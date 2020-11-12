from functools import partial

from .errors import MissingNode, MissingFields
from .utils import import_string, get_first_of


class RootNode:

    def __init__(self, nodes, ctx=None):
        nodes = [import_string(n) if isinstance(n, str) else n for n in nodes]
        self.nodes = {c.Meta.name: c for c in nodes}
        self.ctx = ctx

    def query(self, query):
        """
        query = {'book': {'kwargs': {}, 'fields': `query`}}
        """
        return {
            field: self.solve(field, **data)
            for field, data in query.items()
        }

    def solve(self, field, **data):
        node = self.nodes.get(field)
        if not node or not node.Meta.exposed:
            raise MissingNode(field)
        return node(self.ctx, self.nodes).query(**data)


class Node:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Collect the registered fields
        public_fields = [f for f in dir(cls) if not f.startswith('_')]
        cls._fields = {
            field_name: getattr(cls, field_name)
            for field_name in public_fields
            if isinstance(getattr(cls, field_name), Field)
        }
        # Tell the fields their names
        for field_name, field in cls._fields.items():
            field.name = field_name

    class Meta:
        exposed = True
        name = ''
        source = ()

    def __init__(self, ctx, nodes):
        self.ctx = ctx
        self.nodes = nodes

    def query(self, kwargs, fields, source=None):
        self.check_if_requesting_missing_fields(fields)
        source = self.Meta.source if source is None else source
        items = self.filter(_source=source, **kwargs)
        return (self.serialize(item, fields) for item in items)

    def check_if_requesting_missing_fields(self, fields):
        fields_to_solve = {
            f: v
            for f, v in fields.items()
            if f in self._fields
        }
        missing_fields = set(fields) - set(fields_to_solve)
        if missing_fields:
            raise MissingFields(self.Meta.name, missing_fields)

    def filter(self, _source, **kwargs):
        return _source

    def serialize(self, item, item_fields):
        result = {}
        for field_name, data in item_fields.items():
            kwargs = data.get('kwargs', {})
            fields = data.get('fields', {})

            value = self.resolve(item, field_name, kwargs)
            node = self.get_node_for(field_name)
            if value is not None and node:
                value = self.serialize_related_field(value, node, fields, data)

            result[field_name] = value
        return result

    def serialize_related_field(self, value, node, fields, data):
        if fields:
            if node.is_collection(value):
                value = node.query(source=value, **data)
            else:
                value = node.serialize(value, fields)
        else:
            if node.is_collection(value):
                value = [v.id for v in value]
            else:
                value = value.id
        return value

    def resolve(self, item, field_name, kwargs):
        return self._fields[field_name].resolve(self, item, kwargs)

    def get_node_for(self, field_name):
        field = self._fields[field_name]
        OtherNode = self.nodes.get(field.node_type)
        if OtherNode:
            return OtherNode(self.ctx, self.nodes)

    def is_collection(self, value):
        return isinstance(value, (list, tuple, set))


class Field:
    def __init__(self, node_type=None, prefetch=None):
        self.node_type = node_type
        if isinstance(prefetch, str):
            prefetch = (prefetch,)
        self.prefetch = prefetch

    def __call__(self, resolver):
        self.resolver = resolver
        return self

    def resolve(self, node: Node, instance, kwargs):
        value = partial(self.resolver, node, instance)
        if callable(value):
            value = value(**kwargs)
        return value

    def resolver(self, node, instance, **kwargs):
        return get_first_of(instance, self.name)
