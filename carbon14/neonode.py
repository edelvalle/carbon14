from collections import defaultdict
from functools import partial

from .errors import MissingNode, MissingFields
from .utils import import_string


class RootNode:

    def __init__(self, nodes, ctx=None):
        nodes = [import_string(n) if isinstance(n, str) else n for n in nodes]
        self.nodes = {c.Meta.name: c for c in nodes}
        self.ctx = ctx

    def query(self, query):
        """
        query = {'book': {'kwargs': {}, 'fields': `query`}}
        """
        results = defaultdict(lambda: defaultdict(dict))
        for field, data in query.items():
            self.solve(results, field, **data)
        return results

    def solve(self, results, field, **data):
        node = Mutations if field == 'mutations' else self.nodes.get(field)
        if not node or not node.Meta.exposed:
            raise MissingNode(field)
        return node(self.ctx, self.nodes).query(results, **data)


class Node:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Collect the registered fields
        public_fields = [f for f in dir(cls) if not f.startswith('_')]
        cls._fields_names = tuple(
            field_name
            for field_name in public_fields
            if isinstance(getattr(cls, field_name), Field)
        )
        # Tell the fields their names
        for field_name in cls._fields_names:
            field = getattr(cls, field_name)
            field.name = field_name

        # Collect mutations
        cls._mutations = {
            field_name: getattr(cls, field_name).__annotations__['return']
            for field_name in public_fields
            if getattr(getattr(cls, field_name), 'is_mutation', False)
        }

    class Meta:
        exposed = True
        name = ''
        source = ()

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
            if f in self._fields_names
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
        return getattr(self, field_name).resolve(self, item, kwargs)

    def get_node_for(self, field_name):
        field = getattr(self, field_name)
        OtherNode = self.nodes.get(field.type)
        if OtherNode:
            return OtherNode(self.ctx, self.nodes)

    def is_collection(self, value):
        return isinstance(value, (list, tuple, set))


class Field:
    def __init__(self, a_type: type, prefetch=None):
        self.name = None
        self.type = a_type
        if isinstance(prefetch, str):
            prefetch = (prefetch,)
        self.prefetch = prefetch

    def resolve(self, node: Node, instance, kwargs):
        resolver = getattr(node, f'resolve_{self.name}', None)
        if resolver:
            value = partial(resolver, instance)
        else:
            value = getattr(instance, self.name, None)

        if callable(value):
            value = value(**kwargs)

        return value


class Mutations(Node):
    class Meta(Node.Meta):
        exposed = True
        name = 'mutations'

    def __init__(self, ctx, nodes):
        super().__init__(ctx, nodes)
        self._fields_names = self.nodes.keys()

    def query(self, results, kwargs, fields, source=None):
        for node_name, node_mutations in fields.items():
            node_results = {}
            node = self.nodes.get(node_name)
            if node:
                node_mutations = node_mutations.get('fields', {})
                node_results = dict(self.solve_mutations(node, node_mutations))
            else:
                raise MissingFields(self.Meta.name, node_name)
            results[self.Meta.name][node_name] = node_results
        return results

    def solve_mutations(self, node, node_mutations):
        node = node(self.ctx, self.nodes)
        for mutation_name, data in node_mutations.items():
            return_type = node._mutations.get(mutation_name)
            if return_type:
                kwargs = data.get('kwargs', {})
                value = getattr(node, mutation_name)(**kwargs)
                ReturnNode = self.nodes.get(return_type)
                if ReturnNode:
                    return_node = ReturnNode(self.ctx, self.nodes)
                    fields = data.get('fields', {})
                    value = self.serialize(value, return_node, fields)
                yield mutation_name, value
            else:
                raise MissingFields(
                    f'mutations.{node.Meta.Name}', mutation_name
                )

    def serialize(self, value, node, fields):
        if value is not None and node:
            results = defaultdict(lambda: defaultdict(dict))
            if node.is_collection(value):
                value = node.query(
                    results, source=value, kwargs={}, fields=fields
                )
                value = [v['id'] for v in value]
            else:
                value = node.serialize(results, value, fields)
                value = value['id']
            return results
        return value


def mutation(f):
    f.is_mutation = True
    return f
