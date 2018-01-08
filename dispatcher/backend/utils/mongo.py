from pymongo import MongoClient
from pymongo.database import Database as BaseDatabase
from pymongo.collection import Collection as BaseCollection


class Client(MongoClient):
    def __init__(self):
        super().__init__(host='mongo')


class Database(BaseDatabase):
    def __init__(self):
        super().__init__(Client(), 'Zimfarm')


class Users(BaseCollection):
    username = 'username'
    email = 'email'
    password_hash = 'password_hash'
    is_admin = 'is_admin'

    schema = {
        username: {
            'type': 'string',
            'regex': '^[a-zA-Z0-9_.+-]+$',
            'required': True
        },
        email: {
            'type': 'string',
            'regex': '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        },
        password_hash: {
            'type': 'string',
            'required': True
        },
        is_admin: {
            'type': 'boolean',
            'required': True
        }
    }

    def __init__(self):
        super().__init__(Database(), 'users')


class Tasks(BaseCollection):
    def __init__(self):
        super().__init__(Database(), 'tasks')

    schema = {
        'status': {
            'type': 'string',
            'minlength': 1,
            'maxlength': 25,
            'required': True
        },
        'created': {
            'type': 'datetime',
            'required': True
        },
        'started': {
            'type': 'datetime',
            'nullable': True,
            'required': True
        },
        'finished': {
            'type': 'datetime',
            'nullable': True,
            'required': True
        },
        'offliner': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'minlength': 1,
                    'maxlength': 50,
                    'required': True
                },
                'config': {
                    'type': 'dict',
                }
            }
        },
        'steps': {
            'type': 'list'
        }
    }
