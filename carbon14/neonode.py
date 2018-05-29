from collections import defaultdict
from functools import partial

from .errors import MissingNode, MissingFields
from .utils import import_string


class RootNode:

    def __init__(self, nodes, ctx=None):
        nodes = [import_string(n) if isinstance(n, str) else n for n in nodes]
        self.nodes = self.validate_nodes({c.Meta.name: c for c in nodes})
        self.ctx = ctx

    def validate_nodes(self, nodes):
        for node in nodes.values():
            for nested_field, node_name in node.Meta.nested_fields.items():
                if node_name not in nodes:
                    raise MissingNode(node_name)
        return nodes

    def query(self, query):
        """
        query = {'book': {'kwargs': {}, 'fields': `query`}}
        """
        results = defaultdict(lambda: defaultdict(dict))
        for field, data in query.items():
            self.solve(results, field, **data)
        return results

    def solve(self, results, field, **data):
        node = self.nodes.get(field)
        if not node or not node.Meta.exposed:
            raise MissingNode(field)
        return node(self.ctx, self.nodes).query(results, **data)


class Node:

    class Meta:
        exposed = True
        name = ''
        source = ()
        fields = ('id',)
        nested_fields = {}

    def __init__(self, ctx, nodes):
        self.ctx = ctx
        self.nodes = nodes

    def query(self, results, kwargs, fields, source=None):
        self.check_if_requesting_missing_fields(fields)
        source = self.Meta.source if source is None else source
        items = self.filter(_source=source, **kwargs)
        return [self.serialize(results, item, fields) for item in items]

    def check_if_requesting_missing_fields(self, fields):
        fields_to_solve = {
            f: v
            for f, v in fields.items()
            if f in self.Meta.fields or f in self.Meta.nested_fields
        }
        missing_fields = set(fields) - set(fields_to_solve)
        if missing_fields:
            raise MissingFields(self.Meta.name, missing_fields)

    def filter(self, _source, **kwargs):
        return _source

    def serialize(self, results, item, item_fields):
        result = {'id': self.resolve_id(item)}
        for field_name, data in item_fields.items():
            kwargs = data.get('kwargs', {})
            fields = data.get('fields', {})

            value = self.resolve(item, field_name, kwargs)
            node = self.get_node_for(field_name)
            if value is not None and node:
                if node.is_collection(value):
                    value = node.query(results, source=value, **data)
                    value = [v['id'] for v in value]
                else:
                    value = node.serialize(results, value, fields)
                    value = value['id']

            result[field_name] = value

        results[self.Meta.name][result['id']].update(result)
        return result

    def resolve_id(self, item):
        return item.id

    def resolve(self, item, field_name, kwargs):
        resolver = getattr(self, f'resolve_{field_name}', None)
        if resolver:
            value = partial(resolver, item)
        else:
            value = getattr(item, field_name, None)

        if callable(value):
            value = value(**kwargs)

        return value

    def get_node_for(self, field_name):
        node_name = self.Meta.nested_fields.get(field_name)
        if node_name:
            OtherNode = self.nodes[node_name]
            return OtherNode(self.ctx, self.nodes)

    def is_collection(self, value):
        return isinstance(value, (list, tuple, set))
