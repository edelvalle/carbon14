from xoutil.decorator.meta import decorator

from django.conf import settings
from django.utils import timezone

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import BaseParser
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ParseError

from .graphql import parse
from .errors import Carbon14Error
from .neonode import RootNode, Collection, Field


collections = {}


@decorator
def expose(collection: Collection, name) -> Collection:
    collections[name] = collection()
    return collection


class GraphQLParser(BaseParser):

    media_type = 'application/graphsql'
    renderer_class = JSONRenderer

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)
        try:
            data = stream.read().decode(encoding)
            return parse(data)
        except Carbon14Error as e:
            raise ParseError(str(e))


class ModelCollection(Collection):

    _auth_required = True

    def _resolve(self, instances, ctx, ids=None, **kwargs):
        if self._auth_required and not ctx.user.is_authenticated():
            instances = instances.none()
        else:
            if ids is not None:
                instances = instances.filter(id__in=ids)
        return instances


class GraphQLView(APIView):

    parser_classes = (
        GraphQLParser,
    )

    def post(self, request):
        root_node = RootNode(**collections)
        data = root_node.serialize(children=request.data, ctx=request)
        return Response(data)


class DateTime(Field):

    def serialize(self, instance, children, **kwargs):
        value = super().serialize(instance, children, **kwargs)
        value = value and timezone.localtime(value)
        return value
