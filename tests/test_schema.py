
from carbon14.schema import Schema, ValidationError, And, Or, Optional


def test_type_schemas():
    s = Schema(int)
    assert s.validate(3) == 3
    try:
        s.validate('sdf')
    except ValidationError as e:
        assert e.errors == ["'sdf' is not a valid 'int'"], e.errors
    return s


def test_iterables():
    s = Schema([int])
    assert s.validate([1, 2, 3]) == [1, 2, 3]
    try:
        s.validate(1)
    except ValidationError as e:
        assert e.errors == ["1 is not a valid List"]
    else:
        assert False

    try:
        s.validate(['1'])
    except ValidationError as e:
        assert e.errors == ["'1' is not a valid 'int'"]
    else:
        assert False
    return s


def test_dictionaries():
    s = Schema({'a': int, 'b': str})
    assert s.validate({'a': 1, 'b': 'x'}) == {'a': 1, 'b': 'x'}

    try:
        s.validate({})
    except ValidationError as e:
        assert e.errors == {
            'a': ['This field is missing'],
            'b': ['This field is missing'],
        }
    else:
        assert False

    try:
        s.validate({'a': 3})
    except ValidationError as e:
        assert e.errors == {
            'b': ['This field is missing'],
        }
    else:
        assert False

    try:
        s.validate({'a': 'astirng', 'b': 3})
    except ValidationError as e:
        assert e.errors == {
            'a': ["'astirng' is not a valid 'int'"],
            'b': ["3 is not a valid 'str'"]
        }
    else:
        assert False
    return s


def test_and():
    s = And(int, (lambda x: x >= 5, ":P {x} is lower than 5"))
    assert s.validate(8) == 8

    try:
        s.validate('2')
    except ValidationError as e:
        assert e.errors == ["'2' is not a valid 'int'"]
    else:
        assert False

    try:
        s.validate(1)
    except ValidationError as e:
        assert e.errors == [':P 1 is lower than 5']
    else:
        assert False
    return s


def test_or():
    s = Schema({'a': Or(int, str), 'b': str})
    assert s.validate({'a': 1, 'b': 'x'}) == {'a': 1, 'b': 'x'}
    assert s.validate({'a': '1', 'b': 'x'}) == {'a': '1', 'b': 'x'}

    try:
        s.validate({'a': 1.1, 'b': 's'})
    except ValidationError as e:
        assert e.errors == {
            'a': ["1.1 is not a valid 'int'", "1.1 is not a valid 'str'"],
        }
    else:
        assert False
    return s


def test_optional():
    s = Optional(int)
    assert s.validate(None) is None
    assert s.validate(1) is 1

    try:
        s.validate('str')
    except ValidationError as e:
        assert e.errors == [
            "'str' is not a valid 'NoneType'",
            "'str' is not a valid 'int'"
        ]
    else:
        assert False
    return s


def test_optional_key_in_dictionary():
    s = Schema({'a': int, 'b': Optional(str)})
    assert s.validate({'a': 1}) == {'a': 1}
    assert s.validate({'a': 1, 'b': 'str'}) == {'a': 1, 'b': 'str'}

    try:
        assert s.validate({'a': 1, 'b': 1}) == {'a': 1, 'b': 'str'}
    except ValidationError as e:
        assert e.errors == {
            'b': [
                "1 is not a valid 'NoneType'",
                "1 is not a valid 'str'"
            ]
        }

    return s
