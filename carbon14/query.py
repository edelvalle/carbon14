import json

try:
    from django.core.serializers.json import DjangoJSONEncoder
except ImportError:
    DjangoJSONEncoder = None


class F:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.fields = {}

    def __call__(self, _children=(), **kwargs):
        for child in _children:
            self.fields[child] = None
        self.fields.update(kwargs)
        return self

    def __repr__(self):
        return self.serialize()

    def serialize(self, root_level=False):
        q = []
        if self.kwargs:
            q.append(f'({serializer_parameter(self.kwargs)})')

        if self.fields:
            if not root_level:
                q.append(' { ')
            for f_name, field in self.fields.items():
                q.append(f_name)
                if field:
                    q.append(str(field))
            if not root_level:
                q.append(' } ')

        return ' '.join(q)


def serializer_parameter(value):
    if isinstance(value, dict):
        return ', '.join(
            f'{k}: {serializer_parameter(v)}'
            for k, v in value.items()
        )
    elif isinstance(value, F):
        return str(value)
    else:
        return json.dumps(value, cls=DjangoJSONEncoder)

