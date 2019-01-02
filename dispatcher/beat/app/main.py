import os
import sys
from datetime import timedelta
from time import sleep

import amqp
from celery import Celery
from kombu import Queue, Exchange
from pymongo.errors import ServerSelectionTimeoutError

from mongo import Client
from schedules import Scheduler


def check_mongo_booted() -> bool:
    retries = 3
    while retries > 0:
        try:
            client = Client()
            client.server_info()
            return True
        except ServerSelectionTimeoutError:
            retries -= 1
            sleep(10)
    return False


if __name__ == '__main__':
    if not check_mongo_booted():
        sys.exit(1)

    system_username = 'system'
    system_password = os.getenv('SYSTEM_PASSWORD', '')
    url = 'amqp://{username}:{password}@rabbit:5672/zimfarm'.format(username=system_username, password=system_password)

    app = Celery(main='zimfarm', broker=url)

    # configure beat
    app.conf.beat_scheduler = Scheduler
    app.conf.beat_max_loop_interval = timedelta(minutes=2).seconds

    # configure queue
    offliner_exchange = Exchange('offliner', 'topic')
    app.conf.task_queues = [
        Queue('offliner_default', offliner_exchange, routing_key='#'),
        Queue('offliner_small', offliner_exchange, routing_key='small'),
        Queue('offliner_medium', offliner_exchange, routing_key='medium'),
        Queue('offliner_large', offliner_exchange, routing_key='large')
    ]

    retries = 3
    while retries > 0:
        try:
            app.start(argv=['celery', 'beat', '--loglevel', 'debug'])
        except amqp.exceptions.AccessRefused:
            retries -= 1
            sleep(2)
