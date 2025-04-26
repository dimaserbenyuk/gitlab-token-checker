import pytest
import datetime
from unittest.mock import patch, MagicMock

import gitlab_tokens  # Импортируем правильный модуль


@pytest.mark.parametrize("expires_at,expected", [
    ("2099-01-01", False),  # далеко в будущем
    ((datetime.datetime.utcnow() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"), True),  # скоро истекает
    ((datetime.datetime.utcnow() + datetime.timedelta(days=50)).strftime("%Y-%m-%d"), False),  # не скоро
    (None, False),  # нет даты
    ("∞", False),  # бесконечный токен
])
def test_check_expiration(expires_at, expected):
    assert gitlab_tokens.check_expiration(expires_at) == expected


@patch('gitlab_tokens.requests.get')
def test_get_all_projects(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.side_effect = [
        [{'id': 1, 'path_with_namespace': 'group/project'}],  # первая страница
        []  # вторая страница пустая
    ]

    projects = gitlab_tokens.get_all_projects()
    assert len(projects) == 1
    assert projects[0]['id'] == 1


@patch('gitlab_tokens.requests.get')
def test_get_all_groups(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.side_effect = [
        [{'id': 1, 'full_path': 'group'}],
        []
    ]

    groups = gitlab_tokens.get_all_groups()
    assert len(groups) == 1
    assert groups[0]['id'] == 1


@patch('gitlab_tokens.requests.get')
@patch('gitlab_tokens.print_token')
def test_check_personal_tokens(mock_print_token, mock_get):
    token_data = [{
        "id": 123,
        "name": "test token",
        "scopes": ["api"],
        "created_at": "2024-04-01T12:00:00Z",
        "last_used_at": "2024-04-20T12:00:00Z",
        "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
        "active": True,
        "revoked": False,
        "user": {
            "username": "testuser",
            "email": "testuser@example.com"
        }
    }]

    mock_get.return_value.status_code = 200
    mock_get.return_value.json.side_effect = [token_data, []]

    gitlab_tokens.seen_tokens.clear()
    gitlab_tokens.tokens_printed = 0
    gitlab_tokens.check_personal_tokens()

    mock_print_token.assert_called()
    args, kwargs = mock_print_token.call_args
    token = args[0]
    label = kwargs.get('label')

    assert token['id'] == 123
    assert "testuser" in label


@patch('gitlab_tokens.requests.get')
@patch('gitlab_tokens.print_token')
def test_check_project_tokens(mock_print_token, mock_get):
    project_response = [{'id': 1, 'path_with_namespace': 'group/project'}]
    token_response = [{
        "id": 456,
        "name": "project token",
        "scopes": ["read_api"],
        "created_at": "2024-03-01T12:00:00Z",
        "last_used_at": None,
        "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
        "active": True,
        "revoked": False
    }]

    def side_effect(url, headers, timeout):
        if 'projects?' in url:
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = project_response
            return mock
        elif 'access_tokens' in url:
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = token_response
            return mock
        else:
            return MagicMock(status_code=404)

    mock_get.side_effect = side_effect

    gitlab_tokens.seen_tokens.clear()
    gitlab_tokens.tokens_printed = 0
    gitlab_tokens.check_project_tokens()

    mock_print_token.assert_called()
    args, kwargs = mock_print_token.call_args
    token = args[0]
    label = kwargs.get('label')

    assert token['id'] == 456
    assert label == "Project"


@patch('gitlab_tokens.requests.get')
@patch('gitlab_tokens.print_token')
def test_check_group_tokens(mock_print_token, mock_get):
    group_response = [{'id': 2, 'full_path': 'groupname'}]
    token_response = [{
        "id": 789,
        "name": "group token",
        "scopes": ["read_api"],
        "created_at": "2024-03-01T12:00:00Z",
        "last_used_at": None,
        "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
        "active": True,
        "revoked": False
    }]

    def side_effect(url, headers, timeout):
        if 'groups?' in url:
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = group_response
            return mock
        elif 'access_tokens' in url:
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = token_response
            return mock
        else:
            return MagicMock(status_code=404)

    mock_get.side_effect = side_effect

    gitlab_tokens.seen_tokens.clear()
    gitlab_tokens.tokens_printed = 0
    gitlab_tokens.check_group_tokens()

    mock_print_token.assert_called()
    args, kwargs = mock_print_token.call_args
    token = args[0]
    label = kwargs.get('label')

    assert token['id'] == 789
    assert label == "Group"
