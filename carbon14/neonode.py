
from collections import defaultdict
from xoutil.context import context
from xoutil.objects import get_first_of
from xoutil.decorator.meta import decorator

from .errors import MissingCollection, MissingFields


def merge_dicts(dest, source):
    """
    source: {'children': {}, 'parameters': {'ids': [1, 2, 3, 1]}}
    dest: {'children': {'a': {'x': 1}}, 'parameters': {'ids': [1, 1, 4, 1]}}

    output: {'children': {'a': {'x': 1}}, 'parameters': {'ids': [1, 2, 3, 4]}}
    """
    for k, v in source.items():
        if k not in dest:
            dest[k] = v
        else:
            if isinstance(v, list):
                dest[k] = list(set(dest[k]).union(set(v)))
            elif isinstance(v, dict):
                merge_dicts(dest[k], source[k])
    return dest


class All:
    def __contains__(self, *args, **kwargs):
        return True


All = All()


class Field:

    def __init__(self, ref=None, attr=None, call=False, many=False):
        self.attr = attr
        self.call = call
        self.ref = ref
        self.many = many

    def to_value(self, instance, children, **kwargs):
        value = self.serialize(instance, children=children, **kwargs)

        # ask for new items
        if self.ref:
            query = context['carbon14'].children[self.ref]
            merge_dicts(query['children'], children)

            ids = value if self.many else [value]
            ids = set(x for x in ids if x is not None)
            query['parameters']['ids'] = query['parameters']['ids'].union(ids)

        return value

    def serialize(self, instance, children, **kwargs):
        value = get_first_of(instance, self.attr)
        if value and self.call:
            value = value()
        return value


class MethodField(Field):

    def __init__(self, method=None, **kwargs):
        super().__init__(**kwargs)
        self.serialize = method


@decorator
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


class Collection(metaclass=Node):

    _source = ()
    _permitted_fields = None
    _allowed_fields_list = []

    id = Field()

    def _to_value(
            self, collection_name, level, instances=..., children=None,
            **kwargs):
        instances = self._source if instances is ... else instances
        children = children or {}
        children.setdefault('id', {'parameters': {}, 'children': {}})
        self.field_based_access_policy = None
        instances = self._resolve(level, instances, **kwargs)
        children = self._filter_children(children, instances, **kwargs)

        missing_fields = set(children) - set(self._fields)
        if missing_fields:
            raise MissingFields(collection_name, missing_fields)

        return self._serialize(instances, children, ctx=kwargs.get('ctx'))

    def _resolve(self, level, instances, **kwargs):
        return instances

    def _filter_children(self, children, instances, **kwargs):
        return children

    def _serialize(self, instances, children, ctx):
        return [
            {
                child: self._fields[child].to_value(
                    instance,
                    children=query['children'],
                    **dict(query['parameters'], ctx=ctx)
                )
                for child, query in children.items()
                if self.field_is_allowed_and_accessible_according_to_policy(
                    child
                )
            }
            for instance in instances
        ]

    def field_is_allowed_and_accessible_according_to_policy(self, child):
        if child in self._fields:
            if not self._permitted_fields:
                return True
            # FIX : This list includes a list of values instead of
            # values directly. Check get_allowed_field_list method in django.py
            return child in self._allowed_fields_list[0]
        return False


class RootNode:
    def __init__(self, **collections):
        self.collections = collections

    def serialize(self, children, ctx=None):
        results = defaultdict(lambda: defaultdict(dict))
        more_objects_required = True

        level = 0

        while more_objects_required:
            future_children = defaultdict(
                lambda: {
                    'children': {},
                    'parameters': {'ids': set(), 'ctx': ctx},
                }
            )

            with context('carbon14', children=future_children):
                results = self._serialize(level, results, children, ctx)

            more_objects_required = False

            for collection, objs in results.items():
                ids = set(objs)
                parameters = future_children[collection]['parameters']
                parameters['ids'] = parameters['ids'].difference(ids)

            for query in future_children.values():
                if query['parameters']['ids']:
                    more_objects_required = True
                    children = future_children

            level += 1

        return results

    def _serialize(self, level, results, children, ctx):
        for child, query in children.items():
            collection = self.collections.get(child)
            if collection:
                collection_results = collection._to_value(
                    collection_name=child,
                    level=level,
                    children=query['children'],
                    **dict(query['parameters'], ctx=ctx)
                )
                for r in collection_results:
                    results[child][r['id']].update(r)
            else:
                raise MissingCollection(child)
        return results
