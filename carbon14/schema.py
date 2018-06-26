from functools import wraps
from xoutil.names import nameof
from xoutil.objects import memoized_property


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


def identity(x):
    return x


def use_wrapper(f):

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            raise ValidationError(str(e)) from e

    return wrapper


class BaseSchema:
    def __init__(self, *args, **kwargs):
        if self.use:
            self.use = use_wrapper(self.use)
        else:
            self.use = identity

    def validate(self, data):
        return self.use(data)

    @memoized_property
    def use_name(self):
        return nameof(self.use, inner=True)


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
        self.validator_name = nameof(validator, inner=True)
        self.error = error or "This value is incorrect"

    def validate(self, data):
        if self.validator(data):
            return data
        else:
            raise ValidationError(self.error.format(x=data))

    def __repr__(self):
        return 'Check %r' % (self.validator_name,)


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
        errors = []
        for item in data:
            try:
                item_value = self.schema.validate(item)
            except ValidationError as e:
                errors.append(e.errors)
            else:
                errors.append(None)
                results.append(item_value)

        if any(errors):
            raise ValidationError(errors)
        else:
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
    def __init__(self, *schemas, **kwargs):
        self.use = kwargs.get('use')
        self.schemas = []
        for schema in schemas:
            if not isinstance(schema, BaseSchema):
                schema = Schema(schema)
            self.schemas.append(schema)
        super().__init__()

    def validate(self, data):
        for schema in self.schemas:
            data = schema.validate(data)
        return super().validate(data)

    def __repr__(self):
        return 'And %r as %r' % (self.schemas, self.use_name)


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
            return super().validate(data)

    def __repr__(self):
        return 'Or %r as %r' % (self.schemas, self.use_name)


class Optional(BaseSchema):
    def __init__(self, schema=None, use=identity):
        self.use = use
        if schema and not isinstance(schema, BaseSchema):
            schema = Schema(schema)
        self.schema = schema
        super().__init__()

    def validate(self, data):
        if data is None:
            return None
        elif self.schema:
            data = self.schema.validate(data)
        return super().validate(data)

    def __repr__(self):
        if self.schema:
            return 'Optional %r as %r' % (self.schema, self.use_name)
        else:
            return 'Optional as %r' % (self.use_name,)


Number = Or(int, float)
