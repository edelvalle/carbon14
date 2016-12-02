import serpy
from carbon14 import graphql
from carbon14.node import Node


# Models


class Book:
    def __init__(self, title):
        self.title = title


class Author:
    def __init__(self, id, name, is_alive, books):
        self.id = id
        self.name = name
        self.is_alive = is_alive
        self.books = books


AUTHORS = [
    Author(
        id=32,
        name='Grace',
        is_alive=True,
        books=[Book(title='El becheló'), Book(title='Dog and Cat')]
    ),
    Author(
        id=22,
        name='John',
        is_alive=False,
        books=[Book(title='El bocaza'), Book(title='Dungeon')]
    ),
]


# Nodes

class BookNode(Node):

    title = serpy.StrField()

    def resolve(self, instance, parameters, children, context):
        title_contains = parameters.get('title_contains') or ''
        if self.many:
            # filtering
            instance = [
                i for i in instance if title_contains in i.title
            ]
        else:
            if title_contains not in instance.title:
                instance = None
        return instance, children, context


class AuthorNode(Node):

    id = serpy.IntField()
    name = serpy.StrField()
    is_alive = serpy.BoolField()
    books = BookNode(many=True)


class RootNode(Node):
    authors = serpy.MethodField()

    def get_authors(self, instance, *args, **kwargs):
        return AuthorNode(instance=AUTHORS, many=True, *args, **kwargs).data


def execute(query):
    return RootNode(children=graphql.parse(query)).data


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
    """)
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
            books (title_contains: "El") {
                title
            }
        }
    """)
    assert data == {
        'authors': [
            {'id': 32, 'books': [{'title': 'El becheló'}]},
            {'id': 22, 'books': [{'title': 'El bocaza'}]},
        ]
    }
