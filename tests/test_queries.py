from pytest import raises

from carbon14 import graphql
from carbon14.neonode import RootNode, Node
from carbon14.errors import MissingNode, MissingFields

# Models


class Book:
    def __init__(self, id, title, n_pages, author):
        self.id = id
        self.title = title
        self.n_pages = n_pages
        self._author = author

    @property
    def author(self):
        for author in AUTHORS:
            if author.id == self._author:
                return author


class Author:
    def __init__(self, id, name, is_alive, books):
        self.id = id
        self.name = name
        self.is_alive = is_alive
        self._books = books

    @property
    def books(self):
        books = []
        for book in BOOKS:
            if book.id in self._books:
                books.append(book)
        return books


BOOKS = [
    Book(id=1, title='El becheló', n_pages=100, author=32),
    Book(id=2, title='Dog and Cat', n_pages=200, author=32),
    Book(id=3, title='El bocaza', n_pages=300, author=22),
    Book(id=4, title='Dungeon', n_pages=400, author=22),
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

class Books(Node):
    class Meta(Node.Meta):
        name = 'books'
        source = BOOKS
        fields = ('id', 'title', 'n_pages')
        nested_fields = {'author': 'authors'}

    def filter(self, _source, title_contains='', **kwargs):
        return [book for book in _source if title_contains in book.title]


class Authors(Node):
    class Meta(Node.Meta):
        name = 'authors'
        source = AUTHORS
        fields = ('id', 'name', 'is_alive')
        nested_fields = {'books': 'books'}


def execute(query):
    return RootNode([Books, Authors]).query(graphql.parse(query))


# Tests


def test_empty_query():
    assert execute('') == {}


def test_simple_query():
    data = execute("""
        authors {
            name
        }
    """)
    assert data == {
        'authors': {
            22: {'id': 22, 'name': 'John'},
            32: {'id': 32, 'name': 'Grace'},
        },
    }


def test_subquery():
    data = execute("""
        authors {
            books {
                title
            }
        }
    """)
    assert data == {
        'authors': {
            22: {'books': ('books', [3, 4]), 'id': 22},
            32: {'books': ('books', [1, 2]), 'id': 32},
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
            books (title_contains: "El") {
                title
            }
        }
    """)
    assert data == {
        'authors': {
            22: {'books': ('books', [3]), 'id': 22},
            32: {'books': ('books', [1]), 'id': 32},
        },
        'books': {
            1: {'id': 1, 'title': 'El becheló'},
            3: {'id': 3, 'title': 'El bocaza'},
        },
    }


def test_with_subquery_and_another_query_to_check_interpolation():
    data = execute("""
        authors {
            books (title_contains: "El") {
                title
            }
        }
        books { n_pages }
    """)
    assert data == {
        'authors': {
            22: {'books': ('books', [3]), 'id': 22},
            32: {'books': ('books', [1]), 'id': 32},
        },
        'books': {
            1: {'id': 1, 'title': 'El becheló', 'n_pages': 100},
            2: {'id': 2, 'n_pages': 200},
            3: {'id': 3, 'title': 'El bocaza', 'n_pages': 300},
            4: {'id': 4, 'n_pages': 400},
        },
    }


def test_inverse_subquery_with_parameters():
    data = execute("""
        books (title_contains: "El") {
            title
            author {
                name
            }
        }
    """)

    from pprint import pprint
    pprint(data)
    assert data == {
        'books': {
            1: {'id': 1, 'title': 'El becheló', 'author': ('authors', 32)},
            3: {'id': 3, 'title': 'El bocaza', 'author': ('authors', 22)},
        },
        'authors': {
            22: {'name': 'John', 'id': 22},
            32: {'name': 'Grace', 'id': 32},
        },
    }, data


def test_query_for_missing_collections():
    with raises(MissingNode):
        execute("""
            coco {
                id
            }
        """)


def test_query_for_missing_attributes():
    with raises(MissingFields):
        execute("""
            books {
                misingattr
            }
        """)
