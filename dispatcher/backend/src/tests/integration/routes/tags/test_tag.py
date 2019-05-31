import pytest


class TestTagsList:
    def test_list_tags_no_param(self, client, access_token, schedules):
        """Test list tags"""

        url = '/api/tags/'
        response = client.get(url, headers={'Authorization': access_token})
        assert response.status_code == 200

        response_json = response.get_json()
        assert 'items' in response_json
        assert len(response_json['items']) == 4
        for item in response_json['items']:
            assert isinstance(item, str)

    @pytest.mark.parametrize('skip, limit, expected', [
        (0, 1, 1), (1, 10, 3),
        (0, 100, 4), ('', 10, 4), (5, 'abc', 0)
    ])
    def test_list_tags_with_param(self, client, access_token, schedules, skip, limit, expected):
        """Test list languages with skip and limit"""

        url = '/api/tags/?skip={}&limit={}'.format(skip, limit)
        response = client.get(url, headers={'Authorization': access_token})
        assert response.status_code == 200

        response_json = response.get_json()
        assert 'items' in response_json
        assert len(response_json['items']) == expected

    def test_unauthorized(self, client):
        url = '/api/tags/'
        response = client.get(url)
        assert response.status_code == 401
        assert response.get_json() == {'error': 'token invalid'}
