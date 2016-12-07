
from collections import defaultdict


class Field:

    def __init__(self, ref=None, attr=None, call=False):
        self.attr = attr
        self.call = call
        self.ref = ref

    def to_value(self, instance, children, parameters, ctx=None):
        return self.serialize(instance, children, ctx)

    def serialize(self, instance, children, ctx):
        value = getattr(instance, self.attr, None)
        if value and self.call:
            value = value()
        return value


class MethodField(Field):

    def __init__(self, method=None, **kwargs):
        super().__init__(**kwargs)
        self.method = method

    def to_value(self, instance, children, parameters, ctx=None):
        return self.method(
            instance,
            ctx=ctx,
            **parameters
        )


def field(fn, *args, **kwargs):
    return MethodField(method=fn, *args, **kwargs)


class Node(type):

    def __new__(cls, name, bases, attrs):
        fields = {}
        for field_name, field in attrs.items():
            if isinstance(field, Field):
                field.attr = field.attr or field_name
                fields[field_name] = field

        attrs['_fields'] = fields

        real_class = super().__new__(cls, name, bases, attrs)
        return real_class


class Collection(Field, metaclass=Node):

    def to_value(self, children, parameters, ctx=None):
        parameters = parameters or {}
        instances, children = self.resolve(children, ctx=ctx, **parameters)
        return self.serialize(instances, children, ctx)

    def resolve(self, children, ctx, **kwargs):
        return [], children

    @classmethod
    def references(cls):
        return {
            field_name: field.ref
            for field_name, field in cls._fields.items()
        }

    def serialize(self, instances, children, ctx):
        data = [
            {
                child: self._fields[child].to_value(i, ctx=ctx, **query)
                for child, query in children.items()
            }
            for i in instances
        ]

        new_query = defaultdict(
            lambda: {'children': {}, 'parameters': {'ids': []}}
        )

        for field_name, collection in self.references():
            for item in data:
                field_value = item[field_name]
                if field_value is not None:
                    if not isinstance(field_value, (list, tuple)):
                        field_value = (field_value,)
                    collection_query = new_query[collection]
                    collection_query['children'].update(children[field_name])
                    collection_query['parameters']['ids'].extend(field_value)

        return {item['id']: item for item in data}, new_query


class RootNode(metaclass=Node):

    def serialize(self, children, ctx=None, result=None):
        result = result or defaultdict(dict)

        new_children = defaultdict(
            lambda: {'children': {}, 'parameters': {'ids': []}}
        )

        for child, query in children.items():
            field = self._fields[child]
            field_value, new_query = field.to_value(**query, ctx=ctx)
            result[child].update(field_value)
            for collection, query in new_query.items():
                query[''] result[collection]:
                    item['id']
                collection_query = new_children[collection]

                new_children[collection]['children'].update(query['children'])
                new_children[collection]['parameters'].update(query['parameters']['ids'])



        query = {
            collection: {
                'children': children[collection]['children'],
                'parameters': {'ids': ids},
            }
            for collection, ids in to_serialize.items()
        }

        if to_serialize:
            result = self.serialize(query, ctx, result=result)

        return result
