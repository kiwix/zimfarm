import os, base64, json
import urllib.request, urllib.response


def get_request(path: str, method: str, payload: {}=None):
    username = os.getenv('DISPATCHER_USERNAME')
    password = os.getenv('DISPATCHER_PASSWORD')
    encoded = base64.b64encode(bytes('{}:{}'.format(username, password), 'utf-8')).decode()

    headers = {'Authorization': 'Basic {}'.format(encoded)}

    if payload is None:
        data = None
    else:
        headers['content-type'] = 'application/json'
        data = json.dumps(payload).encode('utf-8')
    return urllib.request.Request('http://rabbit:15672/api' + path, data=data, headers=headers, method=method)


def put_user(username: str, password: str, tag: str) -> int:
    request = get_request('/users/' + username, 'PUT', {'password': password, 'tags': tag})
    with urllib.request.urlopen(request) as response:
        return response.getcode()


def put_permission(vhost:str, username: str, configure: str='.*', write: str='.*', read: str='.*') -> int:
    path = '/{}/{}/{}'.format('permissions', vhost, username)
    payload = {
        'configure': configure,
        'write': write,
        'read': read,
    }
    request = get_request(path, 'PUT', payload)
    with urllib.request.urlopen(request) as response:
        return response.getcode()


def delete_user(username: str) -> int:
    request = get_request('/users/' + username, 'DELETE')
    with urllib.request.urlopen(request) as response:
        return response.getcode()