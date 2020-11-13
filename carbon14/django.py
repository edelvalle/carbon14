from __future__ import annotations

from django import forms
from django.db.models import QuerySet, Prefetch
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.core.exceptions import ValidationError

from rest_framework.views import APIView

from .graphql import parse
from .errors import Carbon14Error
from . import neonode
from . import json


class Field(neonode.Field):
    def resolve(self, node: Node, instance, kwargs):
        value = super().resolve(node, instance, kwargs)

        all_values = getattr(value, 'all', None)
        if all_values:
            value = all_values()

        return value

    def optimize(self, source, *args, **kwargs):
        return source


class A(Field):
    def __init__(self, node_type=None, select=None):
        super().__init__(node_type)
        select = select or node_type
        if isinstance(select, str):
            select = (select,)
        self.select = select

    def optimize(self, source, prefix, data, node=None):
        for select in self.select:
            source = source.select_related(prefix + self.name)
        return source


class Many(Field):
    def __init__(self, node_type=None, prefetch=None):
        super().__init__(node_type)
        if isinstance(prefetch, str):
            prefetch = (prefetch,)
        self.prefetch = prefetch

    def optimize(self, source, prefix, data, node=None):
        if self.prefetch:
            for pretech in self.prefetch:
                source = source.prefetch_related(prefix + self.name)
        elif node:
            source = source.prefetch_related(
                Prefetch(
                    prefix + self.name,
                    queryset=node.filter(
                        node.Meta.source,
                        **data['kwargs']
                    )
                )
            )
            source = node.query_optimization(
                source,
                data['fields'],
                prefix=prefix + self.name + '__',
            )
        return source


class Node(neonode.Node):

    class Meta(neonode.Node.Meta):
        is_public = False
        field_class = Field

    def query(self, kwargs, fields, source=None):
        if source is None:
            source = self.query_optimization(self.Meta.source, fields)
            source = self.filter(source, **kwargs)

        limit = kwargs.get('limit')
        offset = kwargs.get('offset')
        if offset:
            source = source[offset:]

        if limit:
            source = source[:limit]

        return [self.serialize(item, fields) for item in source]

    def query_optimization(self, source: QuerySet, fields, prefix=''):
        self.check_if_requesting_missing_fields(fields)
        for field_name, data in fields.items():
            source = self._fields[field_name].optimize(
                source,
                prefix,
                data,
                node=self.get_node_for(field_name),
            )
        return source

    def filter(self, _source: QuerySet, ids=None, **kwargs) -> QuerySet:
        if not self.Meta.is_public and not self.ctx.user.is_authenticated:
            _source = _source.none()

        if ids is not None:
            _source = _source.filter(id__in=ids)

        return _source

    def is_collection(self, value):
        return isinstance(value, QuerySet) or super().is_collection(value)


class GrapQLForm(forms.Form):
    query = forms.CharField(widget=forms.Textarea)


class GraphQLView(APIView):

    nodes = tuple()

    @property
    def template(self):
        return Template('''
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8" />
              <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
              <meta
                name="viewport"
                content="width=device-width,
                initial-scale=1,
                minimum-scale=1,
                maximum-scale=1"
              >
              <title>Carbon14</title>
            </head>
            <body>

              <form>
                {{ form }}
                <input type="submit" value="Query">
              </form>

              <pre>{{ answer|safe }}</pre>

            </body>
            </html>

        ''')

    def get(self, request):
        query = request.GET.get('query') or ''
        root_node = neonode.RootNode(self.nodes, ctx=request)
        try:
            data = root_node.query(parse(query))
        except Carbon14Error as e:
            data = {'details': str(e)}
            status = 400
        except ValidationError as e:
            data = dict(e)
            status = 400
        else:
            status = 200

        pure_json = 'text/html' not in request.META.get('HTTP_ACCEPT')
        indent = None if pure_json else 2
        data = json.dumps(data, indent=indent)
        if pure_json:
            return HttpResponse(
                data,
                status=status,
                content_type='application/json',
            )
        else:
            form = GrapQLForm(data=request.GET)
            return HttpResponse(self.render(form=form, answer=data))

    def render(self, **kwargs):
        return (
            self.template.render(RequestContext(self.request, kwargs)).encode()
        )
