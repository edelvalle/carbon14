import json
from uuid import UUID

from functools import partial

from schema import Schema, SchemaMissingKeyError

from django import forms
from django.db.models import QuerySet, Prefetch
from django.db.transaction import atomic
from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from django.template import Template, RequestContext
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.csrf import csrf_exempt

from .graphql import parse
from .errors import Carbon14Error
from . import neonode


class Node(neonode.Node):

    class Meta(neonode.Node.Meta):
        is_public = False

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
            fields_to_prefetch = getattr(self, field_name).prefetch

            for f in fields_to_prefetch or ():
                source = source.prefetch_related(prefix + f)

            # Related pre-fetch
            node = self.get_node_for(field_name)
            if node:
                if fields_to_prefetch is None:
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
                    prefix=field_name + '__'
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


class Field(neonode.Field):
    def resolve(self, node: Node, instance, kwargs):
        resolver = getattr(node, f'resolve_{self.name}', None)
        if resolver:
            kwargs = self.validate(resolver, kwargs)
            value = partial(resolver, instance)
        else:
            value = getattr(instance, self.name, None)

        all_values = getattr(value, 'all', None)
        if all_values:
            value = all_values()
        elif callable(value):
            value = value(**kwargs)

        if isinstance(value, UUID):
            value = str(value)

        return value

    def validate(self, resolver, kwargs):
        schema = Schema(resolver.__annotations__, ignore_extra_keys=True)

        try:
            kwargs = dict(kwargs, **schema.validate(kwargs))
        except SchemaMissingKeyError as error:
            keys = str(error)[len('Missing keys: '):].split(', ')
            keys = [k.strip("'") for k in keys]
            error.autos
        return kwargs


class FileField(neonode.Field):
    def __init__(self, a_type=str, *args, **kwargs):
        super().__init__(a_type, *args, **kwargs)

    def resolve(self, *args, **kwargs):
        value = super().resolve(*args, **kwargs)
        if value:
            return value.url


class StringField(neonode.Field):
    def __init__(self, a_type=str, *args, **kwargs):
        super().__init__(a_type, *args, **kwargs)

    def resolve(self, node, instance, *args, **kwargs):
        return str(instance)


class GrapQLForm(forms.Form):
    query = forms.CharField(widget=forms.Textarea)


class GraphQLView(View):

    encoder_class = DjangoJSONEncoder
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

              <form method="post">
                {{ form }}
                {% csrf_token %}
                <input type="submit" value="Query">
              </form>

              <pre>{{ answer|safe }}</pre>

            </body>
            </html>

        ''')

    def get(self, request):
        return HttpResponse(content=self.render(form=GrapQLForm()))

    def post(self, request):
        is_graphql = request.META.get('CONTENT_TYPE') == 'application/graphql'

        if is_graphql:
            query = request.body.decode()
        else:
            form = GrapQLForm(data=request.POST)
            form.is_valid()
            query = form.cleaned_data['query']

        root_node = neonode.RootNode(self.nodes, ctx=request)
        try:
            with atomic():
                data = root_node.query(parse(query))
        except Carbon14Error as e:
            data = {'details': str(e)}
            status = 400
        except ValidationError as e:
            data = dict(e)
            status = 400
        else:
            status = 200

        if is_graphql:
            return JsonResponse(
                data,
                status=status,
                encoder=self.encoder_class
            )
        else:
            data = json.dumps(
                data,
                cls=self.encoder_class,
                indent=2
            )
            return HttpResponse(
                content=self.render(answer=data, form=form),
                status=status,
            )

    def render(self, **kwargs):
        return (
            self.template.render(RequestContext(self.request, kwargs)).encode()
        )
