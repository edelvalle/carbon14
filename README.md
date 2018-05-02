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
    """Describe how to retrieve and expose authors

    Id you want to do permission checking during filtering or computing  any
    custom field remember that `self.ctx` in Django refers to the request object
    so. Using `self.ctx.user` you can know the user that is querying.

    """

    class Meta(ModelNode.Meta):
        # name for this node type
        name = 'authors'  
        
        # the data source when queried in the root level
        source = Author.objects.all()  
        
        # exposed fields
        fields = (
            'id', 
            'first_name', 
            'last_name', 
            'full_name', 
            'is_alive', 
            'description',
        )
        
        # exposed fields that refer to another Node type
        nested_fields = {'books': 'books', 'kill': 'authors'}
        
        # is this node accessible by Anonymous user? (default: False)
        is_public = True

        # is this node exposed in the RootNode? (default: True)
        exposed = True

        # by default ModelNode will do some query optimization when querying
        # related data. But if you wans to specify that when querying
        # `description` the query should pre-fetch the books do this:
        optimize = {'description': 'books'}


    def resolve_full_name(self, author, lower=False, **kwargs):
        """
        Custom field of this node, needs to be listed in `fields` or
        `nested_fields` to be exposed. It can receive parameters.

        Query examples:

        Being author: {id: 1, first_name: 'Alex', last_name: `von Baum`}
        Query: `authors { full_name }`
        Output: `{'authors': {'1': {'full_name': 'Alex von Baum'}}}``

        Query: `authors { full_name (lower: true) }`
        Output: `{'authors': {'1': {'full_name': 'alex von baum'}}}``

        If you want to return a object from another node list this field
        in `nested_fields` and point to the kind of node it returns.

        Note that this kind of field can be used for mutations, because
        it gets called every time is exposed. Check `resolve_kill`
        """
        full_name = f'{author.first_name} {author.last_name}'
        if lower:
            full_name = full_name.lower()
        return full_name

    def resolve_description(self, author, **kwargs):
        return f'Author of: {author.books.all()}'

    def resolve_kill(self, author, **kwargs)
        """Mutation over author

        This kind of mutation can be called as:

        Query: `authors { kill }`

        **It can be also implemented in the Author model class.
        """
        author.is_alive = False
        author.save()
        return author

    def filter(self, _source, name_startswith='', **kwargs):
        """Filtering function.

        The argument  `kwargs` are the arguments passed to this node like here `name_startswith`: 

        Query: `authors (name_startswith='Abc') { title }`
        
        You can manage visibility and permissions here end in the fields because
        `self.ctx` is the request made, so `self.ctx.user` is the user querying
    
        """
        if name_startswith:
            _source = _source.filter(first_name__startswith=name_startswith) 
        return _source
```

## Testing

Install the package in development mode:

    $ python setup.py develop


Install `py.test` and run:

    $ py.test
