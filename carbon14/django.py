from functools import partial

from django.conf import settings
from django.db.models import QuerySet

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import BaseParser
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ParseError

from .graphql import parse
from .errors import Carbon14Error
from .neonode import RootNode, Node


class GraphQLParser(BaseParser):

    media_type = 'application/graphql'
    renderer_class = JSONRenderer

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)
        try:
            data = stream.read().decode(encoding)
            return parse(data)
        except Carbon14Error as e:
            raise ParseError(str(e))


class ModelNode(Node):

    class Meta(Node.Meta):
        is_public = False
        optimize = {}

    def query(self, results, kwargs, fields, source=None):
        if source is None:
            source = self.query_optimization(self.Meta.source, fields)
        return super().query(results, kwargs, fields, source=source)

    def query_optimization(self, source, fields, prefix=''):
        for field_name, data in fields.items():
            if field_name in self.Meta.nested_fields:
                source = source.prefetch_related(field_name)

            for f in self.Meta.optimize.get(field_name, []):
                source = source.prefetch_related(prefix + f)

            node = self.get_node_for(field_name)
            if node:
                source = node.query_optimization(
                    source,
                    data['fields'],
                    prefix=field_name + '__'
                )
        return source

    def filter(self, _source, ids=None, limit=None, offset=None, **kwargs):
        instances = _source
        if not self.Meta.is_public and not self.ctx.user.is_authenticated:
            instances = instances.none()

        if ids is not None:
            instances = instances.filter(id__in=ids)

        if offset:
            instances = instances[offset:]

        if limit:
            instances = instances[:limit]

        return instances

    def resolve(self, item, field_name, kwargs):
        resolver = getattr(self, f'resolve_{field_name}', None)
        if resolver:
            value = partial(resolver, item)
        else:
            value = getattr(item, field_name, None)

        all_values = getattr(value, 'all', None)
        if all_values:
            value = all_values()
        elif callable(value):
            value = value(**kwargs)
        return value

    def is_collection(self, value):
        return isinstance(value, QuerySet) or super().is_collection(value)

    def resolve_id(self, item):
        return str(item.id)


class GraphQLView(APIView):

    parser_classes = (
        GraphQLParser,
    )
    nodes = tuple()

    def post(self, request):
        root_node = RootNode(self.nodes, ctx=request)
        try:
            data = root_node.query(request.data)
        except Carbon14Error as e:
            return Response(
                {'details': str(e)},
                status=400
            )
        else:
            return Response(data)
