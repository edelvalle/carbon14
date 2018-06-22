
from xoutil.names import nameof
from xoutil.decorator import memoized_property


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

    @memoized_property
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
