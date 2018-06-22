
import re
import json
from collections import namedtuple
from functools import lru_cache


from .errors import TokenizerError, LexicalError


Token = namedtuple('Token', ['kind', 'value', 'line', 'column'])


TOKENS = (
    ('BRACKET_OPEN', r'{'),
    ('BRACKET_CLOSE', r'}'),
    ('PARENTHESIS_OPEN', r'\('),
    ('PARENTHESIS_CLOSE', r'\)'),
    ('SQUARE_BRACKET_OPEN', r'\['),
    ('SQUARE_BRACKET_CLOSE', r'\]'),
    ('NULL', r'null'),
    ('BOOL', r'(true|false)'),
    ('NAME', r'[a-zA-Z_]\w*'),
    ('COLON', r':'),
    ('COMMA', r','),
    ('NUMBER', r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?'),
    ('STRING', r'\"([^\\\"]|\\.)*\"'),
    ('NEW_LINE', r'\n'),
    ('WHITE_SPACE', r'\s+'),
    ('MISMATCH', r'.'),
)

TOKEN_REGEX = re.compile('|'.join('(?P<%s>%s)' % pair for pair in TOKENS))


def tokenize(string):
    line_num = 1
    line_start = 0
    tokens = []
    for mo in TOKEN_REGEX.finditer(string):
        kind = mo.lastgroup
        value = mo.group(kind)
        column = mo.start() - line_start + 1
        if kind == 'NEW_LINE':
            line_start = mo.end()
            line_num += 1
        elif kind == 'WHITE_SPACE':
            pass
        elif kind == 'MISMATCH':
            raise TokenizerError(value, line_num, column)
        else:
            tokens.append(Token(kind, value, line_num, column))

    # add first {
    tokens.insert(0, Token('BRACKET_OPEN', '{', 1, 0))

    # add last }
    last_token = tokens[-1]
    tokens.append(Token(
        'BRACKET_CLOSE', '}', last_token.line, last_token.column + 1
    ))
    return tuple(tokens)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.cursor = 0

    @property
    def current(self):
        try:
            return self.tokens[self.cursor]
        except IndexError:
            last_token = self.tokens[-1] if self.tokens else None
            if last_token:
                raise LexicalError(
                    value=last_token.value,
                    line=last_token.line,
                    column=last_token.column,
                )
            else:
                raise LexicalError()

    def consume(self, kinds, null=False):
        if isinstance(kinds, str):
            kinds = [kinds]
        if self.current.kind in kinds:
            token = self.current
            self.cursor += 1
            return token
        if not null:
            raise LexicalError(
                value=self.current.value,
                line=self.current.line,
                column=self.current.column,
                expected_kinds=kinds,
            )

    def parse(self):
        return self.parse_fields({})

    def parse_fields(self, ast):
        """ FIELDS := { ENTRY* } """
        token = self.consume('BRACKET_OPEN', null=True)
        if token:
            while self.current.kind != 'BRACKET_CLOSE':
                ast = self.parse_entry(ast)
            self.consume('BRACKET_CLOSE')
        return ast

    def parse_entry(self, ast):
        """ ENTRY := PARAMETERS FIELDS """
        token = self.consume('NAME')
        ast[token.value] = {
            'kwargs': self.parse_kwargs({}),
            'fields': self.parse_fields({}),
        }
        return ast

    def parse_kwargs(self, ast):
        """ KWARGS := ( [PARAMETER[,]]* )
            KWARGS := null
        """
        token = self.consume('PARENTHESIS_OPEN', null=True)
        if token:
            while self.current.kind != 'PARENTHESIS_CLOSE':
                ast = self.parse_parameter(ast)
                comma = self.consume('COMMA', null=True)
                if not comma:
                    break
            self.consume('PARENTHESIS_CLOSE')
        return ast

    def parse_parameter(self, ast):
        """ PARAMETER := NAME : VALUE """
        name = self.consume('NAME')
        self.consume('COLON')
        ast[name.value] = self.consume_value()
        return ast

    def consume_value(self):
        """ VALUE = STRING | NUMBER | BOOL | NULL | LIST | DICT """
        if self.current.kind == 'SQUARE_BRACKET_OPEN':
            return self.consume_list()
        elif self.current.kind == 'BRACKET_OPEN':
            return self.consume_dict()
        else:
            token = self.consume(['STRING', 'NUMBER', 'BOOL', 'NULL'])
        return json.loads(token.value)

    def consume_list(self):
        """ LIST = [ [VALUE[,]]* ] """
        the_list = []
        self.consume('SQUARE_BRACKET_OPEN')
        while self.current.kind != 'SQUARE_BRACKET_CLOSE':
            the_list.append(self.consume_value())
            comma = self.consume('COMMA', null=True)
            if not comma:
                break
        self.consume('SQUARE_BRACKET_CLOSE')
        return the_list

    def consume_dict(self):
        """ DICT = { [(STRING|NAME): VALUE[,]]* } """
        the_dict = {}
        self.consume('BRACKET_OPEN')
        while self.current.kind != 'BRACKET_CLOSE':
            key = self.consume(['STRING', 'NAME'])
            if key.kind == 'STRING':
                key = key.value.strip('"')
            else:
                key = key.value
            self.consume('COLON')
            the_dict[key] = self.consume_value()
            comma = self.consume('COMMA', null=True)
            if not comma:
                break
        self.consume('BRACKET_CLOSE')
        return the_dict


@lru_cache()
def parse(query):
    tokens = tokenize(query)
    return Parser(tokens).parse()
