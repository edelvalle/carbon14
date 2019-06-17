import json
from uuid import UUID

from functools import partial
from typing import Generator

from django import forms
from django.db.models import QuerySet, Prefetch, Model
from django.db.transaction import atomic
from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from django.template import Template, RequestContext
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.csrf import csrf_exempt



from .graphql import parse
from .errors import Carbon14Error
from .utils import get_first_of
from . import neonode
from . import schema


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
                    prefix=field_name + '__',
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

    def save_related_field(self, instance, name, items):
        ids = filter(None, [item.get('id') for item in items])
        getattr(instance, name).exclude(id__in=ids).delete()
        return self.collect_errors(
            self.set_related(instance, name),
            items,
            name
        )

    def collect_errors(self, action, items, errors_name):
        results = []
        errors = []
        for item in items:
            try:
                results.append(action(item))
            except ValidationError as e:
                errors.append(dict(e))
            else:
                errors.append(None)

        if any(errors):
            raise schema.ValidationError({errors_name: errors})
        else:
            return results

    def set_related(self, instance, name):
        related_field = getattr(instance, name)

        def corrutine(item):
            id = item.pop('id')
            new_item, created = related_field.update_or_create(
                id=id,
                defaults=item,
            )
            new_item.full_clean()
            return new_item

        return corrutine


class Field(neonode.Field):
    def resolve(self, node: Node, instance, kwargs):
        if self.resolver:
            kwargs = self.validate(self.resolver, kwargs)
            value = partial(self.resolver, node, instance)
        else:
            value = get_first_of(instance, self.name)

        all_values = getattr(value, 'all', None)
        if all_values:
            value = all_values()
        elif callable(value):
            value = value(**kwargs)

        if isinstance(value, UUID):
            value = str(value)

        return value


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


class CarbonJSONEncoder(DjangoJSONEncoder):

    def default(self, o):
        if isinstance(o, Model):
            return o.pk

        if isinstance(o, (Generator, set)):
            return list(o)

        if hasattr(o, 'geojson'):
            return json.loads(o.geojson)

        try:
            from numpy import ndarray
        except ImportError:
            pass
        else:
            if isinstance(o, ndarray):
                return list(o)

        return super().default(o)


class GraphQLView(View):

    encoder_class = CarbonJSONEncoder
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
        except schema.ValidationError as e:
            data = e.errors
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
