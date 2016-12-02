from xoutil.decorator.meta import decorator

from django.conf import settings
from django.utils import timezone

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import BaseParser
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ParseError

from serpy import StrField

from .graphql import parse
from .errors import Carbon14Error
from .node import Node


class RootNode(Node):

    def to_value(self, *args, **kwargs):
        response = {}
        for child, query in self._children.items():
            response[child] = getattr(self, child).to_value(
                context=self._context, **query
            )
        return response


@decorator
def expose(node: Node, name, *args, **kwargs) -> Node:
    setattr(RootNode, name, node(*args, **kwargs))
    return node


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


class GraphQLView(APIView):

    parser_classes = (
        GraphQLParser,
    )

    def post(self, request):
        return Response(RootNode(children=request.data, context=request).data)


class DateTime(StrField):
    to_value = staticmethod(timezone.localtime)
