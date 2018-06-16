import json
from functools import lru_cache

try:
    from django.core.serializers.json import DjangoJSONEncoder
except ImportError:
    DjangoJSONEncoder = None


@lru_cache()
def q(_field, *fields, **kwargs):
    query = _field

    if kwargs:
        query += f' ({serializer_parameter(kwargs).strip("{}")})'

    if fields:
        query += ' { ' + ' '.join(fields) + ' } '

    return query


def serializer_parameter(value):
    if isinstance(value, dict):
        return ', '.join(
            f'{k}: {serializer_parameter(v)}'
            for k, v in value.items()
        )
    else:
        return json.dumps(value, cls=DjangoJSONEncoder)
