import logging
from datetime import datetime

from celery import Celery
from celery.events.state import State, Worker

import mongo


class Monitor:
    logger = logging.getLogger(__name__)

    def __init__(self, celery: Celery):
        self.celery = celery
        self.state: State = celery.events.State()

    def start(self):
        with self.celery.connection() as connection:
            handlers = {
                'worker-online': self._worker_online,
                'worker-heartbeat': self._worker_heartbeat,
                'worker-offline': self._worker_offline,
                '*': self.handle_others}
            receiver = self.celery.events.Receiver(connection, handlers=handlers)
            receiver.capture(limit=None, timeout=None, wakeup=True)

    def _worker_online(self, event):
        self.state.event(event)
        worker: Worker = self.state.workers.get(event['hostname'])
        self.logger.debug('Worker online: {}'.format(worker.hostname))

        workers = mongo.Workers()
        filter = {'hostname': worker.hostname}
        update = {
            '$set': {
                'status': worker.status_string.lower(),
                'session': {
                    'online': datetime.fromtimestamp(worker.heartbeats[-1]) if worker.heartbeats else datetime.now(),
                    'offline': None,
                    'processed': worker.processed
                },
                'heartbeats': [],
                'load_average': {
                    '1_min': [],
                    '5_mins': [],
                    '15_mins': []
                }
            }
        }
        workers.update_one(filter, update, upsert=True)

    def _worker_heartbeat(self, event):
        self.state.event(event)
        worker: Worker = self.state.workers.get(event['hostname'])
        self.logger.info('Worker heartbeat: {}'.format(worker.hostname))

        if worker.loadavg:
            load_average = [[load] for load in worker.loadavg]
        else:
            load_average = [[None], [None], [None]]

        filter = {'hostname': worker.hostname}
        update = {'$set': {
            'status': worker.status_string.lower(),
            'session.processed': worker.processed
        }}
        if len(worker.heartbeats) == 1:
            # if we only have one heartbeat, wipe out history
            update['$set']['heartbeats'] = [datetime.fromtimestamp(heartbeat) for heartbeat in worker.heartbeats]
            update['$set']['load_average'] = dict(zip(['1_min', '5_mins', '15_mins'], load_average))
        else:
            # if we have multiple heartbeats already, append to database
            update['$push'] = {
                'heartbeats': {
                    '$each': [datetime.fromtimestamp(worker.heartbeats[-1])],
                    '$slice': -60
                }
            }
            load_average_tags = ['1_min', '5_mins', '15_mins']
            for index, tag in enumerate(load_average_tags):
                path = 'load_average.{}'.format(tag)
                update['$push'][path] = {
                    '$each': load_average[index],
                    '$slice': -60
                }

        workers = mongo.Workers()
        workers.update_one(filter, update, upsert=True)

    def _worker_offline(self, event):
        self.state.event(event)
        worker: Worker = self.state.workers.get(event['hostname'])
        self.logger.info('Worker offline: {}'.format(worker.hostname))

    def handle_others(self, event):
        print('others')
        pass