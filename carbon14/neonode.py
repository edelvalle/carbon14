
from collections import defaultdict
from xoutil.context import context
from xoutil.decorator.meta import decorator


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

    def __init__(self, ref=None, attr=None, call=False, many=True):
        self.attr = attr
        self.call = call
        self.ref = ref
        self.many = many

    def to_value(self, instance, children, **kwargs):
        value = self.serialize(instance, children, **kwargs)

        # ask for new items
        if self.ref:
            query = context['carbon14'].children[self.ref]
            merge_dicts(query['children'], children)

            if not self.many:
                value = [value]

            collection = context['carbon14'].collections[self.ref]
            value = [x['id'] for x in collection._to_value(ids=value, **kwargs)]

            query['parameters']['ids'].extend(value)

        return value

    def serialize(self, instance, children, **kwargs):
        value = getattr(instance, self.attr, None)
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

    id = Field()

    def _to_value(self, instances=..., children=None, **kwargs):
        instances = self._source if instances is ... else instances
        children = children or {}
        children.setdefault('id', {'parameters': {}, 'children': {}})

        instances = self._resolve(instances, **kwargs)
        children = self._filter_children(children, instances, **kwargs)

        return self._serialize(instances, children, ctx=kwargs.get('ctx'))

    def _resolve(self, instances, children, **kwargs):
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
            }
            for instance in instances
        ]


class RootNode:
    def __init__(self, **collections):
        self.collections = collections

    def serialize(self, children, ctx=None):
        results = defaultdict(list)
        solved_ids = defaultdict(set)

        more_objects_required = True

        while more_objects_required:
            future_children = defaultdict(
                lambda: {'children': {}, 'parameters': {'ids': [], 'ctx': ctx}}
            )

            with context(
                    'carbon14',
                    children=future_children,
                    collections=self.collections):
                results = self._serialize(results, solved_ids, children, ctx)

            more_objects_required = False

            for collection, ids in solved_ids.items():
                parameters = future_children[collection]['parameters']
                parameters['ids'] = list(set(parameters['ids']).difference(ids))

            for query in future_children.values():
                if query['parameters']['ids']:
                    more_objects_required = True
                    children = future_children

        return results

    def _serialize(self, results, solved_ids, children, ctx):
        for child, query in children.items():
            collection = self.collections[child]
            collection_results = collection._to_value(
                children=query['children'],
                **dict(query['parameters'], ctx=ctx),
            )
            results[child].extend(collection_results)

            collection_ids = {i['id'] for i in collection_results}
            solved_ids[child] = solved_ids[child].union(collection_ids)
        return results
