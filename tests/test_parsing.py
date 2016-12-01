
from carbon14 import graphql
from carbon14.graphql import Token
from carbon14.errors import TokenizerError, LexicalError


def test_tokenizer_with_correct_query():
    query = """
        {
          __schema {
            aName
            queryType (id: 4, a: "asd\\"s", alex: true) {
              name
            }
          }
        }
    """
    expected_tokens = (
        Token(kind='BRACKET_OPEN', value='{', line=2, column=9),
        Token(kind='NAME', value='__schema', line=3, column=11),
        Token(kind='BRACKET_OPEN', value='{', line=3, column=20),
        Token(kind='NAME', value='aName', line=4, column=13),
        Token(kind='NAME', value='queryType', line=5, column=13),
        Token(kind='PARENTHESIS_OPEN', value='(', line=5, column=23),
        Token(kind='NAME', value='id', line=5, column=24),
        Token(kind='COLON', value=':', line=5, column=26),
        Token(kind='NUMBER', value='4', line=5, column=28),
        Token(kind='COMMA', value=',', line=5, column=29),
        Token(kind='NAME', value='a', line=5, column=31),
        Token(kind='COLON', value=':', line=5, column=32),
        Token(kind='STRING', value='"asd\\"s"', line=5, column=34),
        Token(kind='COMMA', value=',', line=5, column=42),
        Token(kind='NAME', value='alex', line=5, column=44),
        Token(kind='COLON', value=':', line=5, column=48),
        Token(kind='BOOL', value='true', line=5, column=50),
        Token(kind='PARENTHESIS_CLOSE', value=')', line=5, column=54),
        Token(kind='BRACKET_OPEN', value='{', line=5, column=56),
        Token(kind='NAME', value='name', line=6, column=15),
        Token(kind='BRACKET_CLOSE', value='}', line=7, column=13),
        Token(kind='BRACKET_CLOSE', value='}', line=8, column=11),
        Token(kind='BRACKET_CLOSE', value='}', line=9, column=9),
    )
    tokens = graphql.tokenize(query)
    assert tokens == expected_tokens


def test_tokenizer_with_syntax_error():
    query = """
        {
          __schema {
            aName +
            queryType (id: -23, a: "asd\\"s", alex: false, null: null) {
              name
            }
          }
        }
    """
    try:
        tuple(graphql.tokenize(query))
    except TokenizerError as e:
        assert e.value == '+'
        assert e.line == 4
        assert e.column == 19
        assert str(e) == 'Syntax error: "+" unexpected at 4:19'
    else:
        assert False, "No TokenizerError found"


def test_parser():
    query = """
        {
          __schema {
            aName
            queryType (id: -23, a: "asd\\"s", alex: false, coco: null) {
              name
            }
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
                            'children': {},git in
                        }
                    }
                }
            }
        }
    }


def test_parser_with_lexic_error():
    query = """
        {
          tasks {{
            code
            name
            steps {
                name
                time
            }
          }
        }
    """
    try:
        graphql.parse(query)
    except LexicalError as e:
        assert e.value == '{'
        assert e.line == 3
        assert e.column == 18
        assert str(e) == 'Unexpected "{" expecting NAME at 3:18'
    else:
        assert False, "No LexicalError found :'("
