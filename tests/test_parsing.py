
from carbon14 import graphql
from carbon14.graphql import Token
from carbon14.errors import TokenizerError, LexicalError


def test_tokenizer_with_correct_query():
    query = """
        __schema {
            aName
            queryType (id: 4, a: "asd\\"s", alex: true) {
                name
            }
        }
    """
    expected_tokens = (
        Token(kind='BRACKET_OPEN', value='{', line=1, column=0),
        Token(kind='NAME', value='__schema', line=2, column=9),
        Token(kind='BRACKET_OPEN', value='{', line=2, column=18),
        Token(kind='NAME', value='aName', line=3, column=13),
        Token(kind='NAME', value='queryType', line=4, column=13),
        Token(kind='PARENTHESIS_OPEN', value='(', line=4, column=23),
        Token(kind='NAME', value='id', line=4, column=24),
        Token(kind='COLON', value=':', line=4, column=26),
        Token(kind='NUMBER', value='4', line=4, column=28),
        Token(kind='COMMA', value=',', line=4, column=29),
        Token(kind='NAME', value='a', line=4, column=31),
        Token(kind='COLON', value=':', line=4, column=32),
        Token(kind='STRING', value='"asd\\\"s"', line=4, column=34),
        Token(kind='COMMA', value=',', line=4, column=42),
        Token(kind='NAME', value='alex', line=4, column=44),
        Token(kind='COLON', value=':', line=4, column=48),
        Token(kind='BOOL', value='true', line=4, column=50),
        Token(kind='PARENTHESIS_CLOSE', value=')', line=4, column=54),
        Token(kind='BRACKET_OPEN', value='{', line=4, column=56),
        Token(kind='NAME', value='name', line=5, column=17),
        Token(kind='BRACKET_CLOSE', value='}', line=6, column=13),
        Token(kind='BRACKET_CLOSE', value='}', line=7, column=9),
        Token(kind='BRACKET_CLOSE', value='}', line=7, column=10),
    )
    tokens = graphql.tokenize(query)
    assert tokens == expected_tokens


def test_tokenizer_with_syntax_error():
    query = """
        __schema {
            aName +
            queryType (id: -23, a: "asd\\"s", alex: false, null: null) {
                name
            }
        }
    """
    try:
        tuple(graphql.tokenize(query))
    except TokenizerError as e:
        assert e.value == '+'
        assert e.line == 3
        assert e.column == 19
        assert str(e) == 'Syntax error: "+" unexpected at 3:19'
    else:
        assert False, "No TokenizerError found"


def test_parser():
    query = """
        __schema {
            aName
            queryType (id: -23, a: "asd\\"s", alex: false, coco: null) {
                name
            }
        }
    """
    result = graphql.parse(query)
    assert result == {
        '__schema': {
            'parameters': {},
            'children': {
                'aName': {
                    'parameters': {},
                    'children': {},
                },
                'queryType': {
                    'parameters': {
                        'id': -23,
                        'a': 'asd"s',
                        'alex': False,
                        'coco': None,
                    },
                    'children': {
                        'name': {
                            'parameters': {},
                            'children': {}
                        }
                    }
                }
            }
        }
    }


def test_parser_with_lexic_error():
    query = """
        tasks {{
            code
            name
            steps {
                name
                time
            }
        }
    """
    try:
        graphql.parse(query)
    except LexicalError as e:
        assert e.value == '{'
        assert e.line == 2
        assert e.column == 16
        assert str(e) == 'Unexpected "{" expecting NAME at 2:16'
    else:
        assert False, "No LexicalError found :'("


def test_parser_with_dict_as_parameter_value():
    query = """coco (param1: {a: "X", x: [1, 2]} ) """
    result = graphql.parse(query)
    assert result == {
        'coco': {
            'parameters': {
                'param1': {
                    'a': 'X',
                    'x': [1, 2],
                }
            },
            'children': {}
        }
    }


def test_parser_with_list_as_parameter_value():
    query = r"""coco (param1: ["a", "X", {x: [1, 2]}] ) """
    result = graphql.parse(query)
    assert result == {
        'coco': {
            'parameters': {
                'param1': [
                    'a',
                    'X',
                    {'x': [1, 2]}
                ]
            },
            'children': {}
        }
    }
