from carbon14 import graphql
from carbon14.neonode import Collection, RootNode, Field, All, field
from carbon14.errors import MissingCollection, MissingFields

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

    _source = BOOKS

    def _resolve(self, level, instances, ctx, ids=All, **kwargs):
        return [i for i in instances if i.id in ids]


class Authors(Collection):

    id = Field()
    name = Field()
    is_alive = Field()
    books = Field(ref='books', many=True)

    _source = AUTHORS

    @field(ref='books', many=True)
    def books(instance, children, title_contains='', *args, **kwargs):
        ids = []
        for book_id in instance.books:
            for book in BOOKS:
                if book.id == book_id and title_contains in book.title:
                    ids.append(book_id)
        return ids

    def _resolve(self, level, instances, ctx, ids=All, **kwargs):
        return [i for i in instances if i.id in ids]


def execute(query):
    return RootNode(
        books=Books(),
        authors=Authors()
    ).serialize(
        children=graphql.parse(query)
    )


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
        'authors': {
            22: {'id': 22, 'name': 'John'},
            32: {'id': 32, 'name': 'Grace'},
        },
    }


def test_subquery():
    data = execute("""
        authors {
            id
            books {
                id
                title
            }
        }
    """)
    assert data == {
        'authors': {
            22: {'books': [3, 4], 'id': 22},
            32: {'books': [1, 2], 'id': 32},
        },
        'books': {
            1: {'id': 1, 'title': 'El becheló'},
            2: {'id': 2, 'title': 'Dog and Cat'},
            3: {'id': 3, 'title': 'El bocaza'},
            4: {'id': 4, 'title': 'Dungeon'},
        },
    }


def test_with_parameters_in_subquery():
    data = execute("""
        authors {
            id
            books (title_contains: "El") {
                id
                title
            }
        }
    """)
    assert data == {
        'authors': {
            22: {'books': [3], 'id': 22},
            32: {'books': [1], 'id': 32},
        },
        'books': {
            1: {'id': 1, 'title': 'El becheló'},
            3: {'id': 3, 'title': 'El bocaza'},
        },
    }


def test_query_for_missing_collections():
    try:
        data = execute("""
            coco {
                id
            }
        """)
    except MissingCollection:
        assert True
    else:
        assert False, data


def test_query_for_missing_attributes():
    try:
        data = execute("""
            books {
                misingattr
            }
        """)
    except MissingFields:
        assert True
    else:
        assert False, data
