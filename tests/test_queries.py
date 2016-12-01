import pytz
from datetime import datetime

import serpy
from carbon14 import graphql
from carbon14.node import Node


# Models

BERLIN_TZ = pytz.timezone('Europe/Berlin')


class Step:
    def __init__(self, name):
        self.name = name


class Task:
    def __init__(self, id, vehicle_type, notes, start_time, steps):
        self.id = id
        self.vehicle_type = vehicle_type
        self.notes = notes
        self.start_time = start_time
        self.steps = steps


TASKS = [
    Task(
        32, 'van', 'notes ', BERLIN_TZ.localize(datetime(2016, 8, 2, 10, 0)),
        steps=[Step('AB'), Step('BC')]
    ),
    Task(
        22, 'bus', None, BERLIN_TZ.localize(datetime(2016, 8, 23, 10, 2)),
        steps=[Step('XY'), Step('YZ')]
    ),
]


# Nodes

class StepNode(Node):

    name = serpy.StrField()


class TaskNode(Node):
    """The serializer schema definition."""
    # Use a Field subclass like IntField if you need more validation.
    id = serpy.IntField()
    vehicle_type = serpy.StrField()
    notes = serpy.StrField(required=False)
    start_time = serpy.StrField()
    steps = serpy.MethodField()

    def get_steps(self, instance, parameters, children, context):
        prefix = parameters.get('name__startswith')
        if prefix:
            steps = [s for s in instance.steps if s.name.startswith(prefix)]
        else:
            steps = instance.steps
        return StepNode(
            instance=steps, many=True,
            parameters=parameters, children=children,
            context=context
        ).data


class RootNode(Node):
    tasks = serpy.MethodField()

    def get_tasks(self, instance, parameters, children, context):
        parameters.setdefault('start_time', datetime.now().date())
        return TaskNode(
            TASKS,
            parameters=parameters,
            children=children,
            many=True
        ).data


def execute(query):
    return RootNode(children=graphql.parse(query)).data


# Tests


def test_empty_query():
    assert execute('{}') == {}


def test_simple_query():
    data = execute("""
    {
        tasks {
            id
            vehicle_type
        }
    }
    """)
    assert data == {
        'tasks': [
            {'id': 32, 'vehicle_type': 'van'},
            {'id': 22, 'vehicle_type': 'bus'},
        ]
    }


def test_subquery():
    data = execute("""
    {
        tasks {
            id
            steps {
                name
            }
        }
    }
    """)
    assert data == {
        'tasks': [
            {'id': 32, 'steps': [{'name': 'AB'}, {'name': 'BC'}]},
            {'id': 22, 'steps': [{'name': 'XY'}, {'name': 'YZ'}]},
        ]
    }


def test_with_parameters_in_subquery():
    data = execute("""
    {
        tasks {
            id
            steps (name__startswith: "A") {
                name
            }
        }
    }
    """)
    assert data == {
        'tasks': [
            {'id': 32, 'steps': [{'name': 'AB'}]},
            {'id': 22, 'steps': []},
        ]
    }
