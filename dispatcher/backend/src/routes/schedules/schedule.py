import trafaret
from flask import request, jsonify, Response

from datetime import datetime
from errors.http import InvalidRequestJSON, ScheduleNotFound
from models.schedule import ScheduleCategory
from common.mongo import Schedules
from .. import authenticate
from ..base import BaseRoute
from .base import URLComponent


class SchedulesRoute(BaseRoute):
    rule = '/'
    name = 'schedules'
    methods = ['GET']

    @authenticate
    def get(self, *args, **kwargs):
        """Return a list of schedules"""

        # unpack url parameters
        skip = request.args.get('skip', default=0, type=int)
        limit = request.args.get('limit', default=20, type=int)
        skip = 0 if skip < 0 else skip
        limit = 20 if limit <= 0 else limit
        categories = request.args.getlist('category')

        # assemble filters
        filter = {}
        if categories:
            filter['category'] = {'$in': categories}

        # get schedules from database
        projection = {
            '_id': 1,
            'category': 1,
            'enabled': 1,
            'name': 1,
            'config': 1,
            'language': 1,
            'most_recent_task': 1,
            'tags': 1
        }
        cursor = Schedules().find(filter, projection).skip(skip).limit(limit)
        schedules = [schedule for schedule in cursor]

        # task this month
        utc_now = datetime.utcnow()
        first_day_this_month = datetime(year=utc_now.year, month=utc_now.month, day=1)
        for schedule in schedules:
            most_recent_task_updated_at = schedule.get('most_recent_task', {}).get('updated_at')
            if most_recent_task_updated_at and most_recent_task_updated_at > first_day_this_month:
                schedule['task_this_month'] = schedule['most_recent_task']
            else:
                schedule['task_this_month'] = None

        return jsonify({
            'meta': {
                'skip': skip,
                'limit': limit,
            },
            'items': schedules
        })


class ScheduleRoute(BaseRoute, URLComponent):
    rule = '/<string:schedule>'
    name = 'schedule'
    methods = ['GET']

    @authenticate
    def get(self, schedule: str, *args, **kwargs):
        """Get schedule object."""

        query = self.get_schedule_query(schedule)
        schedule = Schedules().find_one(query)
        if schedule is None:
            raise ScheduleNotFound()
        else:
            return jsonify(schedule)

    @authenticate
    def patch(self, schedule: str, *args, **kwargs):
        """
        Update properties of a schedule, including:
        - name
        - language
        - category
        - enabled
        """

        try:
            name = trafaret.String(allow_blank=False)
            language = trafaret.String(allow_blank=False)
            category = trafaret.Enum(*ScheduleCategory.all_values())
            validator = trafaret.Dict(
                trafaret.Key('name', optional=True, trafaret=name),
                trafaret.Key('language', optional=True, trafaret=language),
                trafaret.Key('category', optional=True, trafaret=category))

            update = request.get_json()
            update = validator.check(update)

            query = self.get_schedule_query(schedule)
            matched_count = Schedules().update_one(query, {'$set': update}).matched_count

            if matched_count:
                return Response()
            else:
                raise ScheduleNotFound()
        except trafaret.DataError as e:
            raise InvalidRequestJSON(str(e.error))
