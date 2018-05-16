import json
from functools import lru_cache

try:
    from .django import CarbonJSONEncoder
except ImportError:
    CarbonJSONEncoder = json.JSONEncoder


@lru_cache()
def q(_field, *fields, **kwargs):
    query = _field

    if kwargs:
        kwargs = ', '.join(
            f'{k}: {json.dumps(v, cls=CarbonJSONEncoder)}'
            for k, v in kwargs.items()
        )
        query += f'({kwargs})'

    if fields:
        query += ' { ' + ' '.join(fields) + ' } '

    return query
