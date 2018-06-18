from flask import Blueprint, request, jsonify, Response
from jsonschema import validate, ValidationError
from bson.objectid import ObjectId, InvalidId

from utils.mongo import Schedules
from . import access_token_required, errors


blueprint = Blueprint('schedules', __name__, url_prefix='/api/schedules')

mwoffliner_config_schema = {
    "type": "object",
    "properties": {
        "mwUrl": {"type": "string"},
        "adminEmail": {"type": "string"}
    },
    "required": ["mwUrl", "adminEmail"]
}

schedule_schema = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["crontab"]},
        "config": {"type": "object"}
    },
    "required": ["type", "config"],
}

document_schema = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "offliner": {"type": "string", "enum": ["mwoffliner"]},
        "config": {"anyOf": [
            {"$ref": "#/definitions/mwoffliner_config"}
        ]},
        "schedule": schedule_schema
    },
    "required": ["domain", "offliner", "config", "schedule"],
    "additionalProperties": False,
    "definitions": {
        "mwoffliner_config": mwoffliner_config_schema
    }
}


@blueprint.route("/", methods=["GET", "POST"])
@access_token_required
def collection(access_token):
    if request.method == "GET":
        # TODO: check user permission

        # unpack url parameters
        skip = request.args.get('skip', default=0, type=int)
        limit = request.args.get('limit', default=20, type=int)
        skip = 0 if skip < 0 else skip
        limit = 20 if limit <= 0 else limit

        # get schedules from database
        cursor = Schedules().aggregate([
            {'$skip': skip},
            {'$limit': limit},
        ])
        schedules = [schedule for schedule in cursor]

        return jsonify({
            'meta': {
                'skip': skip,
                'limit': limit,
            },
            'items': schedules
        })
    elif request.method == "POST":
        # TODO: check user permission

        # validate request json
        try:
            request_json = request.get_json()
            validate(request_json, document_schema)
        except ValidationError as error:
            raise errors.BadRequest(error.message)

        schedule_id = Schedules().insert_one(request_json).inserted_id
        return jsonify({'_id': schedule_id})


@blueprint.route("/<string:schedule_id>", methods=["GET", "PATCH", "DELETE"])
@access_token_required
def document(schedule_id, access_token):
    # check if schedule_id is valid `ObjectID`
    try:
        schedule_id = ObjectId(schedule_id)
    except InvalidId:
        raise errors.BadRequest(message="Invalid ObjectID")

    if request.method == "GET":
        # TODO: check user permission

        schedule = Schedules().find_one({'_id': schedule_id})
        if schedule is None:
            raise errors.NotFound()
        return jsonify(schedule)
    elif request.method == "DELETE":
        # TODO: check user permission

        deleted_count = Schedules().delete_one({'_id': schedule_id}).deleted_count
        if deleted_count == 0:
            raise errors.NotFound()
        return Response()


@blueprint.route("/<string:schedule_id>/config", methods=["PATCH"])
@access_token_required
def config(schedule_id, access_token):
    # check if schedule_id is valid `ObjectID`
    try:
        schedule_id = ObjectId(schedule_id)
    except InvalidId:
        raise errors.BadRequest(message="Invalid ObjectID")

    # TODO: check user permission

    # validate request json
    try:
        request_json = request.get_json()
        # TODO: add capabilities to validate other offliner config
        del mwoffliner_config_schema['required']
        validate(request_json, mwoffliner_config_schema)
    except ValidationError as error:
        raise errors.BadRequest(error.message)

    Schedules().update_one({'_id': schedule_id}, {'$set': {'config': request_json}})
    return jsonify({'_id': schedule_id})
