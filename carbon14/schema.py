
from xoutil.names import nameof


class ValidationError(Exception):
    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        elif isinstance(errors, (list, tuple, set)):
            errors = flatten(errors)
        self.errors = errors
        super().__init__(str(errors))


def flatten(iterable):
    results = []
    for x in iterable:
        if isinstance(x, (list, tuple, set)):
            results.extend(flatten(x))
        else:
            results.append(x)
    return results


class BaseSchema:
    def validate(self, *args, **kwargs):
        raise NotImplementedError()


class Schema(BaseSchema):
    def __init__(self, schema, error=None):
        if isinstance(schema, tuple):
            self.schema, self.error = schema
        else:
            self.schema = schema
            self.error = error

    @property
    def underlaying_schema(self):
        if isinstance(self.schema, list):
            return List(self.schema[0])
        elif isinstance(self.schema, dict):
            return Dict(self.schema)
        elif isinstance(self.schema, type):
            return Type(self.schema)
        elif callable(self.schema):
            return Callable(self.schema, self.error)
        else:
            return self.schema

    def validate(self, data):
        return self.underlaying_schema.validate(data)

    def __repr__(self):
        return str(self.underlaying_schema)


class Callable(BaseSchema):
    def __init__(self, validator, error):
        self.validator = validator
        self.error = error or "This value is incorrect"

    def validate(self, data):
        if self.validator(data):
            return data
        else:
            raise ValidationError(self.error.format(x=data))


class Type(BaseSchema):
    def __init__(self, type):
        self.type = type
        self.type_name = nameof(self.type, inner=True)

    def validate(self, data):
        if isinstance(data, self.type):
            return data
        else:
            raise ValidationError(
                '%r is not a valid %r' % (data, self.type_name)
            )

    def __repr__(self):
        return 'type %r' % (self.type_name,)


class List(BaseSchema):
    def __init__(self, schema):
        if not isinstance(schema, BaseSchema):
            schema = Schema(schema)
        self.schema = schema

    def validate(self, data):
        if not isinstance(data, (list, tuple, set)):
            raise ValidationError('%r is not a valid List' % (data,))
        results = []
        for item in data:
            results.append(self.schema.validate(item))
        return results

    def __repr__(self):
        return 'List of %r' % (self.schema)


class Dict(BaseSchema):
    def __init__(self, schemas):
        self.schemas = {}
        for k, v in schemas.items():
            if not isinstance(v, BaseSchema):
                v = Schema(v)
            self.schemas[k] = v

    def validate(self, data):
        data = Type(dict).validate(data)
        errors = {}
        result = {}
        for k, schema in self.schemas.items():
            if k not in data:
                if not isinstance(schema, Optional):
                    errors[k] = ['This field is missing']
            else:
                try:
                    result[k] = schema.validate(data[k])
                except ValidationError as e:
                    errors[k] = e.errors
        if errors:
            raise ValidationError(errors)
        else:
            return result

    def __repr__(self):
        return 'Dictionary %r' % (self.schemas,)


class And(BaseSchema):
    def __init__(self, *schemas):
        self.schemas = []
        for schema in schemas:
            if not isinstance(schema, BaseSchema):
                schema = Schema(schema)
            self.schemas.append(schema)

    def validate(self, data):
        for schema in self.schemas:
            data = schema.validate(data)
        return data

    def __repr__(self):
        return 'And %r' % (self.schemas,)


class Or(And):

    def validate(self, data):
        errors = []
        for schema in self.schemas:
            try:
                return schema.validate(data)
            except ValidationError as e:
                errors.append(e.errors)

        if errors:
            raise ValidationError(errors)
        else:
            return data

    def __repr__(self):
        return 'Or %r' % (self.schemas,)


class Optional(BaseSchema):
    def __init__(self, schema):
        self.schema = Or(type(None), schema)

    def validate(self, data):
        return self.schema.validate(data)

    def __repr__(self):
        return 'Optional %r' % (self.schema.schemas[1])


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


def main():
    print(test_type_schemas())
    print(test_iterables())
    print(test_dictionaries())
    print(test_and())
    print(test_or())
    print(test_optional())
    print(test_optional_key_in_dictionary())


if __name__ == '__main__':
    main()
