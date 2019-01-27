import logging

from bson.objectid import ObjectId, InvalidId
from celery.events.state import Task

from mongo import Tasks
from . import BaseHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BaseTaskEventHandler(BaseHandler):
    def __call__(self, event):
        self.state.event(event)

        task: Task = self.state.tasks.get(event['uuid'])
        logger.debug(task.info())
        return task


class TaskSucceededEventHandler(BaseTaskEventHandler):
    def __call__(self, event):
        task = super().__call__(event)

        try:
            task_id = ObjectId(task.uuid)
        except InvalidId:
            return
        logger.debug(task.result)
        Tasks().update_one({'_id': task_id}, {'$set': {'files': task.result}})
