import logging
import datetime
from http import HTTPStatus

import pytz
import pymongo
import trafaret as t
from flask import request, jsonify, make_response, Response

from common.entities import TaskStatus
from common.mongo import RequestedTasks, Schedules, Workers
from utils.offliners import command_information_for
from errors.http import InvalidRequestJSON, TaskNotFound
from routes import authenticate, url_object_id, auth_info_if_supplied
from routes.base import BaseRoute
from routes.errors import NotFound
from utils.broadcaster import BROADCASTER

logger = logging.getLogger(__name__)


class RequestedTasksRoute(BaseRoute):
    rule = "/"
    name = "requested_tasks"
    methods = ["POST", "GET"]

    @authenticate
    def post(self, *args, **kwargs):
        """ Create requested task from a list of schedule_names """

        validator = t.Dict(
            t.Key("schedule_names", optional=False, trafaret=t.List(t.String)),
            t.Key("priority", optional=True, trafaret=t.ToInt(gte=0)),
            t.Key("worker", optional=True, trafaret=t.String()),
        )

        try:
            request_json = validator.check(request.get_json())
        except t.DataError as e:
            raise InvalidRequestJSON(str(e.error))

        schedule_names = request_json["schedule_names"]
        priority = request_json.get("priority", 0)
        worker = request_json.get("worker")

        # verify requested names exists
        if not Schedules().count_documents(
            {"name": {"$in": schedule_names}, "enabled": True}
        ) >= len(schedule_names):
            raise NotFound()

        try:
            username = kwargs["token"].username
        except Exception as exc:
            logger.error("unable to retrieve username from token")
            logger.exception(exc)
            username = None

        now = datetime.datetime.now(tz=pytz.utc)
        requested_tasks = []
        for schedule_name in schedule_names:

            schedule = Schedules().find_one(
                {"name": schedule_name, "enabled": True}, {"config": 1}
            )
            config = schedule.get("config")

            if not config:
                continue

            # build and save command-information to config
            config.update(command_information_for(config))

            document = {
                "schedule_name": schedule_name,
                "status": TaskStatus.requested,
                "timestamp": {TaskStatus.requested: now},
                "events": [{"code": TaskStatus.requested, "timestamp": now}],
                "requested_by": username,
                "priority": priority,
                "worker": worker,
                "config": config,
            }

            if worker:
                document["worker"] = worker

            rt_id = RequestedTasks().insert_one(document).inserted_id
            document.update({"_id": str(rt_id)})
            requested_tasks.append(document)

        if len(requested_tasks) > 1:
            BROADCASTER.broadcast_requested_tasks(requested_tasks)
        elif len(requested_tasks) == 1:
            BROADCASTER.broadcast_requested_task(requested_tasks[0])

        return make_response(
            jsonify({"requested": [rt["_id"] for rt in requested_tasks]}),
            HTTPStatus.CREATED,
        )

    @auth_info_if_supplied
    def get(self, *args, **kwargs):
        """ list of requested tasks """

        # validate query parameter
        request_args = request.args.to_dict()
        request_args["matching_offliners"] = request.args.getlist("matching_offliners")

        validator = t.Dict(
            {
                t.Key("skip", default=0): t.ToInt(gte=0),
                t.Key("limit", default=100): t.ToInt(gt=0, lte=200),
                t.Key("priority", optional=True): t.ToInt(gte=0, lte=10),
                t.Key("worker", optional=True): t.String(),
                t.Key("schedule_name", optional=True): t.String(),
                t.Key("matching_cpu", optional=True): t.ToInt(gte=0),
                t.Key("matching_memory", optional=True): t.ToInt(gte=0),
                t.Key("matching_disk", optional=True): t.ToInt(gte=0),
                t.Key("matching_offliners", optional=True): t.List(
                    t.Enum("mwoffliner", "youtube", "gutenberg", "ted", "phet")
                ),
            }
        )
        request_args = validator.check(request_args)

        # unpack query parameter
        skip, limit = request_args["skip"], request_args["limit"]
        schedule_name = request_args.get("schedule_name")
        priority = request_args.get("priority")
        worker = request_args.get("worker")
        token = kwargs.get("token")

        # record we've seen a worker, if applicable
        if token and worker:
            Workers().update_one(
                {"name": worker, "username": token.username},
                {"$set": {"last_seen": datetime.datetime.now()}},
            )

        # get requested tasks from database
        query = {}
        if schedule_name:
            query["schedule_name"] = schedule_name

        if priority:
            query["priority"] = {"$gte": priority}

        if worker:
            query["worker"] = {"$in": [None, worker]}

        for res_key in ("cpu", "memory", "disk"):
            key = f"matching_{res_key}"
            if key in request_args:
                query[f"config.resources.{res_key}"] = {"$lte": request_args[key]}
        matching_offliners = request_args.get("matching_offliners")
        if matching_offliners:
            query["config.task_name"] = {"$in": matching_offliners}

        cursor = (
            RequestedTasks()
            .find(
                query,
                {
                    "_id": 1,
                    "status": 1,
                    "schedule_name": 1,
                    "config.task_name": 1,
                    "config.resources": 1,
                    "timestamp.requested": 1,
                    "requested_by": 1,
                    "priority": 1,
                    "worker": 1,
                },
            )
            .sort(
                [
                    ("priority", pymongo.DESCENDING),
                    ("timestamp.requested", pymongo.DESCENDING),
                ]
            )
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
    methods = ["GET", "PATCH", "DELETE"]

    @url_object_id("requested_task_id")
    def get(self, requested_task_id: str, *args, **kwargs):

        requested_task = RequestedTasks().find_one({"_id": requested_task_id})
        if requested_task is None:
            raise TaskNotFound()

        return jsonify(requested_task)

    @url_object_id("requested_task_id")
    def patch(self, requested_task_id: str, *args, **kwargs):

        requested_task = RequestedTasks().count_documents({"_id": requested_task_id})
        if not requested_task:
            raise TaskNotFound()

        validator = t.Dict(t.Key("priority", optional=False, trafaret=t.ToInt(gte=0)))

        try:
            request_json = validator.check(request.get_json())
        except t.DataError as e:
            raise InvalidRequestJSON(str(e.error))

        update = RequestedTasks().update_one(
            {"_id": requested_task_id},
            {"$set": {"priority": request_json.get("priority", 0)}},
        )
        if update.modified_count:
            return Response(status=HTTPStatus.ACCEPTED)
        return Response(status=HTTPStatus.OK)

    @authenticate
    @url_object_id("requested_task_id")
    def delete(self, requested_task_id: str, *args, **kwargs):

        query = {"_id": requested_task_id}
        task = RequestedTasks().find_one(query, {"_id": 1})
        if task is None:
            raise TaskNotFound()

        result = RequestedTasks().delete_one(query)
        return jsonify({"deleted": result.deleted_count})
