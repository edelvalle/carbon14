# Carbon 14

This library  QraphQL like query language that exposes the data in a Falcor like format.

Take a look to the tests in the file [`tests/test_queries.py`](tests/test_queries.py)

## Django integration

To integrate with Django you will require Django REST Framework.

Put this in your `urls.py` file, passing in the `nodes` parameters the nodes you will handle in this endpoint.

```python
...

from carbon14.django import GraphQLView

urlpatters = [
    ...
    url(r'graphql/$', GraphQLView.as_view(nodes=[Users, Groups])),
    ...
]

...
```

To expose a resource write the spec for a Node:

```python

from carbon14.neonode import ModelNode
from .models import Author, Book

class Books(ModelNode):
    class Meta(ModelNode.Meta):
        name = 'books'
        source = Books.objects.all()
        fields = ('id', 'title', 'author')
        nested_fields = {'author': 'authors'}


class Authors(ModelNode):
    class Meta(ModelNode.Meta):
        name = 'authors'
        source = Author.objects.all()
        fields = ('id', 'first_name', 'last_name', 'full_name', 'is_alive')
        nested_fields = {'books': 'books'}

    def resolve_full_name(self, author, **kwargs):
        return f'{author.first_name} {author.last_name}'

    def filter(self, _source, name_startswith='', **kwargs):
        if name_startswith:
            _source = _source.filter(first_name__startswith=name_startswith) 
        return _source
```

## Testing

Install the package in development mode:

    $ python setup.py develop


Install `py.test` and run:

    $ py.test
