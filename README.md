# Carbon 14

This library is a GraphQL serializer that exposes the data in a Falcor like format.

Take a look to the tests in the file [`tests/test_queries.py`](tests/test_queries.py)

## Django integration

To integrate with Django you will require Django REST Framework.

Put this in your `urls.py` file

```python
...

from carbon14.django import GraphQLView

urlpatters = [
    ...
    url(r'graphql/$', GraphQLView.as_view()),
    ...
]

...
```

Don't worry about the RootNode, it is created automatically the only thing you need to do is decorate the nodes you want to expose in the RootNode like this:

```python

from carbon14.neonode import Field, Collection
from carbon14.django import expose


class ModelCollection(Collection):

    def _resolve(self, instances, ctx, ids=(), **kwargs):
        """
        @param ctx: is the http request
        """
        if ctx.user.is_authenticated():
            if ids:
                instances = instances.filter(id__in=ids)
            return instances
        else:
            return instances.none()


@expose('books')
class Books(ModelCollection):
    _source = Books.objects.all()

    id = Field()
    title = Field()
    author_id = Field()


@expose('authors')
class Authors(ModelCollection):
    _source = Author.objects.all()

    id = Field()
    name = Field()
    is_alive = Field()
    book_ids = Field(ref='books', many=True)
```

## Testing

Install the package in development mode:


    $ python setup.py develop

Install `py.test` and run:

    $ py.test
