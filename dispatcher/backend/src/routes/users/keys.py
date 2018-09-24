import base64
import binascii
from datetime import datetime

import jsonschema
import paramiko
from bson import ObjectId
from flask import request, jsonify, Response

from routes import authenticate, bson_object_id, errors
from routes.users import url_user
from utils.mongo import Users


@authenticate
@bson_object_id(['user_id'])
def list(user_id: ObjectId, user: dict):
    # TODO: check permission
    ssh_keys = Users().find_one({'_id': user_id}, {'ssh_keys': 1}).get('ssh_keys', [])
    return jsonify(ssh_keys)


@authenticate
@url_user
def add(user_id: ObjectId, username: str):
    # validate request json
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "key": {"type": "string", "minLength": 1}
        },
        "required": ["name", "key"],
        "additionalProperties": False
    }
    try:
        request_json = request.get_json()
        jsonschema.validate(request_json, schema)
    except jsonschema.ValidationError as error:
        raise errors.BadRequest(error.message)

    # parse key
    key = request_json['key']
    key_parts = key.split(' ')
    if len(key_parts) >= 2:
        key = key_parts[1]

    # compute fingerprint
    try:
        rsa_key = paramiko.RSAKey(data=base64.b64decode(key))
        fingerprint = binascii.hexlify(rsa_key.get_fingerprint()).decode()
    except (binascii.Error, paramiko.SSHException):
        raise errors.BadRequest('Invalid RSA key')

    # database
    if user_id is not None:
        filter = {'_id': user_id}
    else:
        filter = {'username': username}

    document = {
        'user_id': user_id,
        'username': username,
        'fingerprint': fingerprint,
        'name': request_json['name'],
        'key': key,
        'added': datetime.now(),
        'last_used': None
    }

    return jsonify(document)
