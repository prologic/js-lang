# -*- encoding: utf-8 -*-


LOAD_CONSTANT, LOAD_VAR, ASSIGN, \
DISCARD_TOP, RETURN, JUMP_IF_FALSE, JUMP_BACKWARD, \
BINARY_ADD, BINARY_SUB, BINARY_EQ, BINARY_LT, \
PRINT \
= range(12)


BINOP = {'+': BINARY_ADD, '-': BINARY_SUB, '==': BINARY_EQ, '<': BINARY_LT}

