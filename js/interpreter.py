# -*- encoding: utf-8 -*-


from rpython.rlib import jit


from js import parser
from js import bytecode
from js.builtins import BUILTINS
from js.base_objects import OperationalError
from js.base_objects import W_FloatObject, W_StringObject, W_Function, W_BuilinFunction


def get_printable_location(pc, code, bc):
    return '%s #%d %s' % (bc.get_repr(), pc, bytecode.dis_one(code[pc]))


jitdriver = jit.JitDriver(
    greens=['pc', 'code', 'bc'],
    reds=['frame'],
    virtualizables=['frame'],
    get_printable_location=get_printable_location)


class Frame(object):

    _virtualizable2_ = ['valuestack[*]', 'valuestack_pos', 'vars[*]',
                        'names[*]', 'parent']

    def __init__(self, bc, parent=None):
        self = jit.hint(self, fresh_virtualizable=True, access_directly=True)
        self.valuestack = [None] * 10  # TODO - get upper bound staticaly
        # TODO - or maybe have even smaller initial estimate and resize when
        # needed?
        self.valuestack_pos = 0
        self.names = bc.names
        self.vars = [None] * len(bc.names)
        self.parent = parent

    def push(self, v):
        pos = self.valuestack_pos
        assert pos >= 0
        self.valuestack[pos] = v
        self.valuestack_pos = pos + 1

    def pop(self):
        new_pos = self.valuestack_pos - 1
        assert new_pos >= 0
        v = self.valuestack[new_pos]
        self.valuestack_pos = new_pos
        return v

    def lookup(self, arg):
        value = self._lookup(arg)
        if value is None:
            name = self.names[arg]
            value = BUILTINS.get(name, None)
            if value is None:
                raise OperationalError('Variable "%s" is not defined' % name)
        return value

    def _lookup(self, arg):
        value = self.vars[arg]
        if value is not None:
            return value
        if self.parent is not None:
            name = self.names[arg]
            return self.parent.lookup_by_name(name)

    def lookup_by_name(self, name):
        # linear search
        for i, n in enumerate(self.names):
            if n == name:
                return self.vars[i]
        if self.parent:
            return self.parent.lookup_by_name(name)

    @jit.unroll_safe
    def call(self, fn, arg_list):
        frame = Frame(fn.bytecode, parent=fn.parent_frame)
        for i, value in enumerate(arg_list):
            frame.vars[i] = value
        return execute(frame, fn.bytecode)

    @property
    def test_valuestack(self):
        ''' NOT_RPYTHON '''

        return self.valuestack[:self.valuestack_pos]


def execute(frame, bc):  # noqa
    code = bc.code
    pc = 0
    while True:
        jitdriver.jit_merge_point(pc=pc, code=code, bc=bc, frame=frame)

        c = ord(code[pc])
        arg = ord(code[pc + 1])
        pc += 2

        if c == bytecode.LOAD_CONSTANT_FLOAT:
            frame.push(W_FloatObject(bc.constants_float[arg]))
        elif c == bytecode.LOAD_CONSTANT_STRING:
            frame.push(W_StringObject(bc.constants_string[arg]))
        elif c == bytecode.LOAD_CONSTANT_FN:
            frame.push(W_Function(bc.constants_fn[arg], frame))
        elif c == bytecode.LOAD_VAR:
            frame.push(frame.lookup(arg))
        elif c == bytecode.ASSIGN:
            frame.vars[arg] = frame.pop()
        elif c == bytecode.DISCARD_TOP:
            frame.pop()

        # TODO - remove repition
        elif c == bytecode.BINARY_ADD:
            right = frame.pop()
            left = frame.pop()
            w_res = left.add(right)
            frame.push(w_res)
        elif c == bytecode.BINARY_SUB:
            right = frame.pop()
            left = frame.pop()
            frame.push(left.sub(right))
        elif c == bytecode.BINARY_MUL:
            right = frame.pop()
            left = frame.pop()
            frame.push(left.mul(right))
        elif c == bytecode.BINARY_DIV:
            right = frame.pop()
            left = frame.pop()
            frame.push(left.div(right))
        elif c == bytecode.BINARY_LT:
            right = frame.pop()
            left = frame.pop()
            frame.push(left.lt(right))
        elif c == bytecode.BINARY_EQ:
            right = frame.pop()
            left = frame.pop()
            frame.push(left.eq(right))
        elif c == bytecode.BINARY_MOD:
            right = frame.pop()
            left = frame.pop()
            frame.push(left.mod(right))
        elif c == bytecode.JUMP_IF_FALSE:
            if not frame.pop().is_true():
                pc = arg
        elif c == bytecode.JUMP_ABSOLUTE:
            pc = arg
        elif c == bytecode.CALL:
            arg_list = pop_args(frame, arg)
            fn = frame.pop()
            if isinstance(fn, W_BuilinFunction):
                frame.push(fn.call(arg_list))
            else:
                frame.push(frame.call(fn, arg_list))
        elif c == bytecode.RETURN:
            if arg:
                return frame.pop()
            else:
                return None  # TODO - undefined
        else:
            assert False


@jit.unroll_safe
def pop_args(frame, n_args):
    arg_list = []
    for _ in xrange(n_args):
        arg_list.append(frame.pop())
    return arg_list


def interpret(bc):
    frame = Frame(bc)
    execute(frame, bc)
    return frame


def interpret_source(source, filename=None):
    ast = parser.parse(source, filename=filename)
    bc = bytecode.CompilerContext.compile_ast(ast)
    return interpret(bc)


def run(source, filename=None):
    try:
        interpret_source(source, filename=filename)
    except parser.LexerError as e:
        print 'LexerError', e
        return 1
    except parser.ParseError as e:
        print 'ParseError', e
        return 1
    except OperationalError as e:
        print e
        return 1
    else:
        return 0
