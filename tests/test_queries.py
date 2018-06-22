from types import GeneratorType
from pytest import raises
from pprint import pprint
from unittest import TestCase

from carbon14 import graphql
from carbon14.neonode import RootNode, Node, Field, mutation
from carbon14.errors import MissingNode, MissingFields
from carbon14.schema import ValidationError

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

            id = Field(int)
            title = Field(str)
            n_pages = Field(int)

            def filter(self, _source, title_contains='', **kwargs):
                return [
                    book
                    for book in _source
                    if title_contains in book.title
                ]

            author = Field('authors')

            def resolve_author(self, book, **kwargs):
                for author in AUTHORS:
                    if author.id == book.author_id:
                        return author

            change_title = Field('books')

            def resolve_change_title(self, instance, title: str):
                instance.title = title
                return instance

        class Authors(Node):
            class Meta(Node.Meta):
                name = 'authors'
                source = AUTHORS

            id = Field(int)
            name = Field(str)
            is_alive = Field(bool)
            books = Field('books')
            kill = Field('authors')

            @mutation('authors')
            def new(self, name, is_alive, books):
                return Author('ID', name, is_alive, books)

        self.root_node = RootNode([Books, Authors])

    def query(self, query):
        return self.ungenerator(self.root_node.query(graphql.parse(query)))

    def ungenerator(self, something):
        if isinstance(something, (list, tuple, GeneratorType)):
            return [self.ungenerator(i) for i in something]
        elif isinstance(something, dict):
            return {k: self.ungenerator(v) for k, v in something.items()}
        else:
            return something

    def test_empty_query(self):
        assert self.query('') == {}

    def test_simple_query(self):
        data = self.query("""
            authors {
                id
                name
            }
        """)
        pprint(data)
        assert data == {
            'authors': [
                {'id': 32, 'name': 'Grace'},
                {'id': 22, 'name': 'John'},
            ],
        }

    def test_subquery(self):
        data = self.query("""
            authors {
                id
                books {
                    title
                }
            }
        """)
        pprint(data)
        assert data == {
            'authors': [
                {
                    'id': 32,
                    'books': [
                        {'title': 'El becheló'},
                        {'title': 'Dog and Cat'},
                    ]
                },
                {
                    'id': 22,
                    'books': [
                        {'title': 'El bocaza'},
                        {'title': 'Dungeon'},
                    ]
                },
            ]
        }

    def test_with_parameters_in_subquery(self):
        data = self.query("""
            authors {
                id
                books (title_contains: "El") {
                    id
                    title
                }
            }
        """)
        assert data == {
            'authors': [
                {
                    'id': 32,
                    'books': [
                        {'id': 1, 'title': 'El becheló'},
                    ]
                },
                {
                    'id': 22,
                    'books': [
                        {'id': 3, 'title': 'El bocaza'},
                    ]
                },
            ]
        }

    def test_with_subquery_and_another_query_to_check_interpolation(self):
        data = self.query("""
            authors {
                id
                books (title_contains: "El") {
                    id
                    title
                }
            }
            books { id n_pages }
        """)
        assert data == {
            'authors': [
                {
                    'id': 32,
                    'books': [
                        {'id': 1, 'title': 'El becheló'},
                    ]
                },
                {
                    'id': 22,
                    'books': [
                        {'id': 3, 'title': 'El bocaza'},
                    ]
                },
            ],
            'books': [
                {'id': 1, 'n_pages': 100},
                {'id': 2, 'n_pages': 200},
                {'id': 3, 'n_pages': 300},
                {'id': 4, 'n_pages': 400},
            ],
        }

    def test_inverse_subquery_with_parameters(self):
        data = self.query("""
            books (title_contains: "El") {
                id
                title
                author {
                    name
                }
            }
        """)
        assert data == {
            'books': [
                {'id': 1, 'title': 'El becheló', 'author': {'name': 'Grace'}},
                {'id': 3, 'title': 'El bocaza', 'author': {'name': 'John'}},
            ]
        }, data

    def test_using_mutations(self):
        data = self.query("""
            authors { id kill { name is_alive } }
        """)
        pprint(data)
        assert data == {
            'authors': [
                {
                    'id': 32,
                    'kill': {
                        'name': 'Grace',
                        'is_alive': False,
                    }
                },
                {
                    'id': 22,
                    'kill': {
                        'name': 'John',
                        'is_alive': False,
                    }
                },
            ]
        }

        data = self.query("authors { is_alive name }")
        assert data == {
            'authors': [
                {
                    'is_alive': False,
                    'name': 'Grace',
                },
                {
                    'is_alive': False,
                    'name': 'John',
                },
            ]
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

    def test_mutation_creating_new_author(self):
        data = self.query("""
            mutations {
                authors {
                    new (name: "Ash", is_alive: false, books: null) {
                        id
                        name
                        is_alive
                    }
                }
            }
        """)
        pprint(data)
        assert data == {
            'mutations': {
                'authors': {
                    'new': {
                        'id': 'ID',
                        'name': 'Ash',
                        'is_alive': False,
                    }
                }
            }
        }

    def test_schema_validation(self):
        data = self.query("""
            books {
                change_title (title: "AA") { id title }
            }
        """)
        assert data == {
            'books': [
                {'change_title': {'id': 1, 'title': 'AA'}},
                {'change_title': {'id': 2, 'title': 'AA'}},
                {'change_title': {'id': 3, 'title': 'AA'}},
                {'change_title': {'id': 4, 'title': 'AA'}}
            ]
        }

    def test_schema_validation_with_bad_input(self):
        try:
            self.query("""
                books {
                    change_title (title: 1) { id title }
                }
            """)
        except ValidationError as error:
            assert error.errors == {
                'title': ["1 is not a valid 'str'"]
            }
        else:
            assert False
