from flask import request, jsonify

from common.mongo import Schedules
from routes import authenticate
from routes.base import BaseRoute


class LanguagesRoute(BaseRoute):
    rule = '/'
    name = 'languages'
    methods = ['GET']

    @authenticate
    def get(self, *args, **kwargs):
        """return a list of languages"""

        # unpack url parameters
        skip = request.args.get('skip', default=0, type=int)
        limit = request.args.get('limit', default=20, type=int)
        skip = 0 if skip < 0 else skip
        limit = 20 if limit <= 0 else limit

        group = {'$group': {
                 '_id': '$language.code',
                 'name_en': {'$first': '$language.name_en'},
                 'name_native': {'$first': '$language.name_native'}}}

        try:
            nb_languages = next(Schedules().aggregate(
                [group, {'$count': 'count'}]))['count']
        except StopIteration:
            nb_languages = 0

        if nb_languages == 0:
            languages = []
        else:
            pipeline = [group,
                        {'$sort': {'_id': 1}},
                        {'$skip': skip},
                        {'$limit': limit}]
            languages = [
                {'code': s['_id'],
                 'name_en': s['name_en'],
                 'name_native': s['name_native']}
                for s in Schedules().aggregate(pipeline)]

        return jsonify({
            'meta': {
                'skip': skip,
                'limit': limit,
                'count': nb_languages,
            },
            'items': languages
        })
