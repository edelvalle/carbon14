from carbon14 import graphql
from carbon14.neonode import Collection, RootNode, Field, field


# Models


class Book:
    def __init__(self, id, title, author):
        self.id = id
        self.title = title
        self.author = author


class Author:
    def __init__(self, id, name, is_alive, books):
        self.id = id
        self.name = name
        self.is_alive = is_alive
        self.books = books


BOOKS = [
    Book(id=1, title='El becheló', author=32),
    Book(id=2, title='Dog and Cat', author=32),
    Book(id=3, title='El bocaza', author=22),
    Book(id=4, title='Dungeon', author=22),
]


AUTHORS = [
    Author(
        id=32,
        name='Grace',
        is_alive=True,
        books=[1, 2]
    ),
    Author(
        id=22,
        name='John',
        is_alive=False,
        books=[3, 4]
    ),
]


# Nodes

class Books(Collection):

    id = Field()
    title = Field()
    author = Field(ref='authors')

    def resolve(self, children, title_contains='', **kwargs):
        return BOOKS, children


class Authors(Collection):

    id = Field()
    name = Field()
    is_alive = Field()

    def resolve(self, children, *args, **kwargs):
        return AUTHORS, children

    @field
    def books(instance, title_contains=None, *args, **kwargs):
        return [
            book.id
            for book in BOOKS
            if title_contains in book.title and book.id in instance.books
        ]


class RootNode(RootNode):
    authors = Authors()
    books = Books()


def execute(query):
    return RootNode().serialize(children=graphql.parse(query))


# Tests


def test_empty_query():
    assert execute('') == {}


def test_simple_query():
    data = execute("""
        authors {
            id
            name
        }
    """)
    from pprint import pprint
    pprint(data)
    assert data == {
        'authors': [
            {'id': 32, 'name': 'Grace'},
            {'id': 22, 'name': 'John'},
        ]
    }


def test_subquery():
    data = execute("""
        authors {
            id
            books {
                title
            }
        }
        books {
            id
            title
        }
    """)
    from pprint import pprint
    pprint(data)
    assert data == {
        'authors': [
            {'id': 32, 'books': [
                {'title': 'El becheló'},
                {'title': 'Dog and Cat'}
            ]},
            {'id': 22, 'books': [
                {'title': 'El bocaza'},
                {'title': 'Dungeon'}
            ]},
        ]
    }


def test_with_parameters_in_subquery():
    data = execute("""
        authors {
            id
            books (title_contains: "El")
        }
        books {
            id
            title
        }
    """)
    from pprint import pprint
    pprint(data)
    assert data == {
        'authors': [
            {'id': 32, 'books': [{'title': 'El becheló'}]},
            {'id': 22, 'books': [{'title': 'El bocaza'}]},
        ]
    }
