
import inspect

import serpy
from serpy.serializer import SerializerMeta


class MetaNode(SerializerMeta):

    @staticmethod
    def _get_fields(*args, **kwargs):
        """Extension of `SerializerMeta._get_fields`.

        The parameter `pass_query` is added to detect if the getter requires
        the query parameters.
        """
        field_map, cmp_fields = SerializerMeta._get_fields(*args, **kwargs)
        fields = []
        for name, getter, to_value, call, required, pass_self in cmp_fields:
            try:
                pass_query = 'parameters' in inspect.getargspec(to_value).args
            except TypeError:  # the callable can't be inspected
                pass_query = False

            fields.append(
                (name, getter, to_value, call, required, pass_self, pass_query)
            )
        return field_map, tuple(fields)


class Node(serpy.Serializer, metaclass=MetaNode):

    def __init__(self, instance=None, parameters=None, children=None,
                 context=None, *args, **kwargs):
        super().__init__(instance=instance, *args, **kwargs)
        self._parameters = parameters
        self._children = children
        self._context = context

    def to_value(
            self, instance=..., parameters=None, children=None, context=None):
        """Re-implementation of `Serializer.to_value`.

        Compute the specific data for the object resolution and call
        `resolve` to do customization of the `instance` and `children` of the
        query based on `parameters` and `context`.
        """

        # get the context
        if instance is ...:
            instance = self.instance

        parameters = parameters or self._parameters or {}
        children = children or self._children or {}
        context = context or self._context

        resolve = self.resolve_many if self.many else self.resolve_one
        instance, children, context = resolve(
            instance, parameters, children, context)

        instance, children, context = self.resolve_always(
            instance, parameters, children, context)

        # filter fields
        fields = [f for f in self._compiled_fields if f[0] in children]

        # serialize
        if self.many:
            serialize = self._serialize
            return [
                serialize(o, fields, children, context)
                for o in instance
            ]
        return self._serialize(instance, fields, children, context)

    def resolve_one(self, instance, parameters, children, context):
        return instance, children, context

    def resolve_many(self, instances, parameters, children, context):
        return instances, children, context

    def resolve_always(self, instance, parameters, children, context):
        return instance, children, context

    def _serialize(self, instance, fields, children, context):
        """Re-implementation of `Serializer._serialize`.

        Serialize `instance` passing the required context to each field
        serializer.

        *This method look like hell because is optimized for speed.
        """
        v = {}
        for name, getter, to_value, call, required, pass_self, pass_q in fields:
            if pass_self:  # is a method of the local class
                result = getter(
                    self, instance, context=context, **children[name]
                )
            else:
                result = getter(instance)
                if required or result is not None:
                    if call:
                        result = result()
                    if to_value:
                        if pass_q:
                            result = to_value(
                                result,
                                context=context,
                                **children[name],
                            )
                        else:
                            result = to_value(result)
            v[name] = result

        return v
