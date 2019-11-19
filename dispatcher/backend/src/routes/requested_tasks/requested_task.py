import logging
import datetime

import pytz
import pymongo
import trafaret as t
from bson import ObjectId
from flask import request, jsonify

from common.entities import TaskStatus
from common.mongo import RequestedTasks, Schedules
from errors.http import InvalidRequestJSON, TaskNotFound
from routes import authenticate, url_object_id
from routes.base import BaseRoute
from routes.errors import NotFound
from common.validators import ObjectIdValidator
from utils.broadcaster import BROADCASTER

logger = logging.getLogger(__name__)


class RequestedTasksRoute(BaseRoute):
    rule = "/"
    name = "requested_tasks"
    methods = ["POST", "GET"]

    @authenticate
    def post(self, *args, **kwargs):
        """ Create requested task from a list of schedule_names """

        request_json = request.get_json()
        if not request_json:
            raise InvalidRequestJSON()
        schedule_names = request_json.get("schedule_names", [])
        if not isinstance(schedule_names, list):
            raise InvalidRequestJSON()

        # verify requested names exists
        if not Schedules().count_documents(
            {"name": {"$in": schedule_names}, "enabled": True}
        ) >= len(schedule_names):
            raise NotFound()

        now = datetime.datetime.now(tz=pytz.utc)
        requested_tasks = []
        for schedule_name in schedule_names:

            schedule = Schedules().find_one(
                {"name": schedule_name, "enabled": True}, {"config": 1}
            )
            config = schedule.get("config")

            if not config:
                continue

            document = {
                "schedule_id": schedule["_id"],
                "schedule_name": schedule_name,
                "status": TaskStatus.requested,
                "timestamp": {TaskStatus.requested: now},
                "events": [{"code": TaskStatus.requested, "timestamp": now}],
                "config": config,
            }
            rt_id = RequestedTasks().insert_one(document).inserted_id
            document.update({"_id": str(rt_id)})
            requested_tasks.append(document)

        if len(requested_tasks) > 1:
            BROADCASTER.broadcast_requested_tasks(requested_tasks)
        elif len(requested_tasks) == 1:
            BROADCASTER.broadcast_requested_task(requested_tasks[0])

        response = jsonify({"requested": requested_tasks})
        response.status_code = 201
        return response

    def get(self, *args, **kwargs):
        """ list of requested tasks """

        # validate query parameter
        request_args = request.args.to_dict()
        validator = t.Dict(
            {
                t.Key("skip", default=0): t.ToInt(gte=0),
                t.Key("limit", default=100): t.ToInt(gt=0, lte=200),
                t.Key("schedule_id", optional=True): ObjectIdValidator,
            }
        )
        request_args = validator.check(request_args)

        try:
            request_json = request.get_json()
        except Exception:
            request_json = None
        if request_json:
            matchingValidator = t.Dict(
                {
                    t.Key("cpu"): t.ToInt(gte=0),
                    t.Key("memory"): t.ToInt(gte=0),
                    t.Key("disk"): t.ToInt(gte=0),
                    t.Key("offliners", optional=True): t.List(
                        t.Enum("mwoffliner", "youtube", "gutenberg", "ted", "phet")
                    ),
                }
            )
            validator = t.Dict({t.Key("matching", optional=True): matchingValidator})
            request_json_args = validator.check(request_json)
        else:
            request_json_args = {}

        # unpack query parameter
        skip, limit = request_args["skip"], request_args["limit"]
        schedule_id = request_args.get("schedule_id")

        # get requested tasks from database
        query = {}
        if schedule_id:
            query["schedule_id"] = ObjectId(schedule_id)

        # matching request (mostly for workers)
        matching_query = {}
        if "matching" in request_json_args:
            for res_key in ("cpu", "memory", "disk"):
                if res_key in request_json_args["matching"]:
                    matching_query[f"config.resources.{res_key}"] = {
                        "$lte": request_json_args["matching"][res_key]
                    }
            if "offliners" in request_json_args["matching"]:
                matching_query["config.task_name"] = {
                    "$in": request_json_args["matching"]["offliners"]
                }

        query.update(matching_query)

        cursor = (
            RequestedTasks()
            .find(
                query,
                {
                    "_id": 1,
                    "status": 1,
                    "schedule_id": 1,
                    "schedule_name": 1,
                    "config.task_name": 1,
                    "config.resources": 1,
                    "timestamp.requested": 1,
                },
            )
            .sort("timestamp.requested", pymongo.DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        count = RequestedTasks().count_documents(query)

        return jsonify(
            {
                "meta": {"skip": skip, "limit": limit, "count": count},
                "items": [task for task in cursor],
            }
        )


class RequestedTaskRoute(BaseRoute):
    rule = "/<string:requested_task_id>"
    name = "requested_task"
    methods = ["GET"]

    @url_object_id("requested_task_id")
    def get(self, requested_task_id: str, *args, **kwargs):

        requested_task = RequestedTasks().find_one({"_id": requested_task_id})
        if requested_task is None:
            raise TaskNotFound()

        return jsonify(requested_task)


class RequestedTaskDeleteRoute(BaseRoute):
    rule = "/<string:requested_task_id>"
    name = "requested_task_delete"
    methods = ["DELETE"]

    @authenticate
    @url_object_id("requested_task_id")
    def delete(self, requested_task_id: str, *args, **kwargs):

        query = {"_id": requested_task_id}
        task = RequestedTasks().find_one(query, {"_id": 1})
        if task is None:
            raise TaskNotFound()

        result = RequestedTasks().delete_one(query)
        return jsonify({"deleted": result.deleted_count})
