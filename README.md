# Carbon 14

This is a library that gives Serpy GraphQL capabilities.

This project contains it's own GraphQL parser and specialization of the Serpy serializer (`Node`) that understands GraphQL queries. 

Disclaimer: As Serpy is not intended to be used for data validation and mutations this library does not provide that either, use just to optimize your read queries and use normal REST API endpoints to implement mutations.

## Example

Take a look to the tests in the file `tests/test_queries.py`

## Django integration

To integrate with Django you will require Django REST Framework.

Put this in your `urls.py` file

```
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

```
@expose('authors', instance=Author.objects.all(), many=True)
class AuthorNode(Node):
    id = serpy.IntField()
    name = serpy.StrField()
    is_alive = serpy.BoolField()
    books = BookNode(many=True)

    def resolve(self, instance, parameters, children, context):
        """Select what to show.

        @param context: is the http request
        """
        # permission checking
        if not context.user.is_athenticated:
            instance = [] if self.many else None

        # filtering
        id = parameters.get('id', None)
        if id:
            if self.many:
                instance = instance.filter(id=id)
            else:
                instance = instance if id == instance.id else None

        # query optimization
        if self.many and 'books' in children:
            instance = instance.prefecth_related('steps')

        return instance, children, context
```

## Testing

Install the package in development mode:

`$ python setup.py develop`

Install `py.test` and run:

`$ py.test`
