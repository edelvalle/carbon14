from __future__ import annotations

from django import forms
from django.db.models import QuerySet, Prefetch
from django.http import HttpResponse
from django.views.generic import View
from django.template import Template, RequestContext
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt

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

            # Explicit prefetch
            fields_to_prefetch = self._fields[field_name].prefetch

            for f in fields_to_prefetch or ():
                source = source.prefetch_related(prefix + f)

            # Related pre-fetch
            node = self.get_node_for(field_name)
            if node and fields_to_prefetch is None:
                source = source.prefetch_related(
                    Prefetch(
                        prefix + field_name,
                        queryset=node.filter(
                            node.Meta.source,
                            **data['kwargs']
                        )
                    )
                )
                source = node.query_optimization(
                    source,
                    data['fields'],
                    prefix=prefix + field_name + '__',
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
    answer_html = forms.CharField(
        widget=forms.HiddenInput,
        initial='yes',
        required=False,
    )


class GraphQLView(View):

    nodes = tuple()

    @classmethod
    def as_view(cls, *args, **kwargs):
        return csrf_exempt(super().as_view(*args, **kwargs))

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
        form = GrapQLForm(data=request.GET)
        form.is_valid()
        query = form.cleaned_data.get('query') or ''

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

        is_graphql = not form.cleaned_data['answer_html']
        if is_graphql:
            data = json.dumps(data)
            return HttpResponse(
                data,
                status=status,
                content_type='application/json',
            )
        else:
            data = json.dumps(data, indent=2)
            return HttpResponse(
                content=self.render(answer=data, form=form),
                status=status,
            )

    def render(self, **kwargs):
        return (
            self.template.render(RequestContext(self.request, kwargs)).encode()
        )
