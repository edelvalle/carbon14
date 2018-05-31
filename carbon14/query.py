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
        kwargs = ', '.join(
            f'{k}: {json.dumps(v, cls=DjangoJSONEncoder)}'
            for k, v in kwargs.items()
        )
        query += f'({kwargs})'

    if fields:
        query += ' { ' + ' '.join(fields) + ' } '

    return query
