from pytest import raises
from unittest import TestCase

from carbon14 import graphql
from carbon14.neonode import RootNode, Node
from carbon14.errors import MissingNode, MissingFields

# Models


class Book:
    def __init__(self, id, title, n_pages, author_id):
        self.id = id
        self.title = title
        self.n_pages = n_pages
        self.author_id = author_id


class Author:
    def __init__(self, id, name, is_alive, books):
        self.id = id
        self.name = name
        self.is_alive = is_alive
        self.books = books

    def kill(self):
        self.is_alive = False
        return self


class TestQueries(TestCase):

    def setUp(self):
        BOOKS = [
            Book(id=1, title='El becheló', n_pages=100, author_id=32),
            Book(id=2, title='Dog and Cat', n_pages=200, author_id=32),
            Book(id=3, title='El bocaza', n_pages=300, author_id=22),
            Book(id=4, title='Dungeon', n_pages=400, author_id=22),
        ]
        AUTHORS = [
            Author(
                id=32,
                name='Grace',
                is_alive=True,
                books=BOOKS[:2]
            ),
            Author(
                id=22,
                name='John',
                is_alive=False,
                books=BOOKS[2:]
            ),
        ]

        class Books(Node):
            class Meta(Node.Meta):
                name = 'books'
                source = BOOKS
                fields = ('id', 'title', 'n_pages')
                nested_fields = {'author': 'authors'}

            def filter(self, _source, title_contains='', **kwargs):
                return [
                    book
                    for book in _source
                    if title_contains in book.title
                ]

            def resolve_author(self, book, **kwargs):
                for author in AUTHORS:
                    if author.id == book.author_id:
                        return author

        class Authors(Node):
            class Meta(Node.Meta):
                name = 'authors'
                source = AUTHORS
                fields = ('id', 'name', 'is_alive')
                nested_fields = {'books': 'books', 'kill': 'authors'}

        self.root_node = RootNode([Books, Authors])

    def query(self, query):
        return self.root_node.query(graphql.parse(query))

    def test_empty_query(self):
        assert self.query('') == {}

    def test_simple_query(self):
        data = self.query("""
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

    def test_subquery(self):
        data = self.query("""
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

    def test_with_parameters_in_subquery(self):
        data = self.query("""
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

    def test_with_subquery_and_another_query_to_check_interpolation(self):
        data = self.query("""
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

    def test_inverse_subquery_with_parameters(self):
        data = self.query("""
            books (title_contains: "El") {
                title
                author {
                    name
                }
            }
        """)
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

    def test_using_mutations(self):
        data = self.query("""
            authors { kill { name is_alive } }
        """)
        assert data == {
            'authors': {
                22: {
                    'id': 22,
                    'kill': ('authors', 22),
                    'is_alive': False,
                    'name': 'John',
                },
                32: {
                    'id': 32,
                    'kill': ('authors', 32),
                    'is_alive': False,
                    'name': 'Grace',
                },
            },
        }

        data = self.query("authors { is_alive name }")
        assert data == {
            'authors': {
                22: {
                    'id': 22,
                    'is_alive': False,
                    'name': 'John',
                },
                32: {
                    'id': 32,
                    'is_alive': False,
                    'name': 'Grace',
                },
            },
        }

    def test_query_for_missing_collections(self):
        with raises(MissingNode):
            self.query("""
                coco {
                    id
                }
            """)

    def test_query_for_missing_attributes(self):
        with raises(MissingFields):
            self.query("""
                books {
                    misingattr
                }
            """)
