import json
from unittest.mock import patch

import pytest
from bson import ObjectId

from common.entities import TaskStatus


class TestTaskCreate:
    @pytest.fixture(scope='session')
    def send_task(self):
        with patch('utils.celery.Celery.send_task_from_schedule') as mocked_send_task:
            yield mocked_send_task

    @pytest.fixture()
    def schedule(self, make_schedule):
        schedule = make_schedule('wikipedia_en')
        return schedule

    def test_create_from_schedule(self, client, access_token, schedule, send_task):
        url = '/api/tasks/'
        headers = {'Authorization': access_token, 'Content-Type': 'application/json'}
        data = json.dumps({'schedule_names': [schedule.get('name')]})
        response = client.post(url, headers=headers, data=data)
        assert response.status_code == 200

        send_task.assert_called_with(schedule['name'])

    @pytest.mark.parametrize('body', [
        None, '', '[]', '{"test": 123}'
    ])
    def test_create_with_bad_body(self, client, access_token, body):
        url = '/api/tasks/'
        response = client.post(url, headers={'Authorization': access_token}, data=body)
        assert response.status_code == 400


class TestTaskList:
    def _assert_task(self, task, item):
        assert set(item.keys()) == {'_id', 'status', 'schedule'}
        assert item['_id'] == str(task['_id'])
        assert item['status'] == task['status']
        assert item['schedule']['_id'] == str(task['schedule']['_id'])
        assert item['schedule']['name'] == task['schedule']['name']

    def test_unauthorized(self, client, tasks):
        url = '/api/tasks/'
        response = client.get(url)
        assert response.status_code == 401

    def test_list(self, client, access_token, tasks):
        tasks = [task for task in tasks if task['status'] not in [TaskStatus.sent, TaskStatus.received]]

        url = '/api/tasks/'
        headers = {'Authorization': access_token, 'Content-Type': 'application/json'}
        response = client.get(url, headers=headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['meta']['limit'] == 100
        assert data['meta']['skip'] == 0

        items = data['items']
        tasks.sort(key=lambda task: task['_id'], reverse=True)
        assert len(items) == len(tasks)
        for index, task in enumerate(tasks):
            item = items[index]
            self._assert_task(task, item)

    def test_list_pagination(self, client, access_token, tasks):
        url = '/api/tasks/?limit={}&skip={}'.format(10, 5)
        headers = {'Authorization': access_token, 'Content-Type': 'application/json'}
        response = client.get(url, headers=headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['meta']['limit'] == 10
        assert data['meta']['skip'] == 5

    @pytest.mark.parametrize('statuses', [[TaskStatus.succeeded], [TaskStatus.succeeded, TaskStatus.received]])
    def test_status(self, client, access_token, tasks, statuses):
        url = f'/api/tasks/?'
        for status in statuses:
            url += f'status={status}&'

        headers = {'Authorization': access_token, 'Content-Type': 'application/json'}
        response = client.get(url, headers=headers)
        assert response.status_code == 200

        tasks = {task['_id']: task for task in tasks if task['status'] in statuses}
        items = json.loads(response.data)['items']

        assert len(tasks) == len(items)
        for item in items:
            task = tasks[ObjectId(item['_id'])]
            self._assert_task(task, item)


class TestTaskGet:
    def test_unauthorized(self, client, task):
        url = '/api/tasks/{}'.format(task['_id'])
        response = client.get(url)
        assert response.status_code == 401

    def test_not_found(self, client, access_token):
        url = '/api/tasks/task_id'
        headers = {'Authorization': access_token, 'Content-Type': 'application/json'}
        response = client.get(url, headers=headers)
        assert response.status_code == 404

    def test_get(self, client, access_token, task):
        url = '/api/tasks/{}'.format(task['_id'])
        headers = {'Authorization': access_token, 'Content-Type': 'application/json'}
        response = client.get(url, headers=headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['_id'] == str(task['_id'])
        assert data['status'] == task['status']
        assert data['schedule']['_id'] == str(task['schedule']['_id'])
        assert data['schedule']['name'] == task['schedule']['name']
        assert 'timestamp' in data
        assert 'events' in data
