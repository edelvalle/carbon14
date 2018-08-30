from xoutil.decorator.meta import decorator
from xoutil.objects import get_first_of

from django.conf import settings
from django.utils import timezone
from django.contrib.gis.geos import Point

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
def expose(collection: Collection, name, *args, **kwargs) -> Collection:
    collections[name] = collection(*args, **kwargs)
    return collection


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


class ModelCollection(Collection):

    _auth_required = True

    def _resolve(
        self,
        level,
        instances,
        ctx,
        ids=None,
        limit=None,
        offset=0,
        sort_order=None,
        use_permissions=True,
        **kwargs
    ):
        """
        :param limit: Determines the maximum number of results for pagination.
        :param offset: Determines the start index of the results for pagination.
        :param sort_order:
        (string) Comma-separated list of Django-like sort instructions.
        A sort instruction consists of a model field name and optionally a
        minus ('-') sign in front to indicate descending sort direction.
        """

        if self._auth_required and not ctx.user.is_authenticated:
            instances = instances.none()
        else:
            if ids is not None:
                instances = instances.filter(id__in=ids)

        if sort_order:
            sort_order_list = sort_order.split(',')
            instances = instances.order_by(*sort_order_list)

        instances = instances.all()[offset:]

        if use_permissions:
            instances = instances.has_permission(ctx.user)

        if limit:
            instances = instances[:limit]

        return instances


class GraphQLView(APIView):

    parser_classes = (
        GraphQLParser,
    )

    def post(self, request):
        root_node = RootNode(**collections)
        try:
            data = root_node.serialize(children=request.data, ctx=request)
        except Carbon14Error as e:
            return Response(
                {'details': str(e)},
                status=400
            )
        else:
            return Response(data)


class DateTime(Field):

    def serialize(self, instance, children, **kwargs):
        value = super().serialize(instance, children, **kwargs)
        value = value and timezone.localtime(value)
        return value


class PointField(Field):
    def serialize(self, instance, *args, **kwargs):
        value = get_first_of(instance, self.attr)
        if isinstance(value, Point):
            value = tuple(value)
        return value
