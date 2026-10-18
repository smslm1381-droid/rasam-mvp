"""دسترسی، بازگشت به گفتگو و خروجی تاریخی از همان API مشترک مک و ویندوز."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from rasam import config
from rasam.core.answer import Answer
from rasam.desktop.app import create_app

HEADERS = {'X-Rasam-Token': 'test-chat-token'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_HOME', tmp_path)
    def answer(question, history=None):
        previous = len(history or [])
        return Answer(question, source=next(iter(config.settings.allowed_sources)),
                      query={'test': True}, rows=[{'previous': previous}], summary=f'قبلی: {previous}')
    return TestClient(create_app('test-chat-token', answer), base_url='http://127.0.0.1', client=('127.0.0.1', 1234))


def test_return_to_chat_after_server_restart_has_context_and_exports(client):
    chat = client.post('/chats', headers=HEADERS).json()['id']
    first = client.post('/ask', headers=HEADERS, json={'question': 'دمای امروز؟', 'chat_id': chat})
    identity = first.headers['X-Answer-ID']
    restarted = TestClient(create_app('test-chat-token', client.app.state.session.answerer), base_url='http://127.0.0.1', client=('127.0.0.1', 1234))
    second = restarted.post('/ask', headers=HEADERS, json={'question': 'حالا دیروز؟', 'chat_id': chat})
    assert second.json()['rows'] == [{'previous': 1}]
    assert len(restarted.get('/chats/' + chat, headers=HEADERS).json()['turns']) == 2
    assert restarted.get(f'/export/{identity}/csv', headers=HEADERS).status_code == 200
    assert restarted.delete('/chats/' + chat, headers=HEADERS).json() is True
    assert restarted.get(f'/export/{identity}/csv', headers=HEADERS).status_code == 404


def test_chat_and_answer_ids_cannot_cross_connections(client, monkeypatch):
    chat = client.post('/chats', headers=HEADERS).json()['id']
    response = client.post('/ask', headers=HEADERS, json={'question': 'q', 'chat_id': chat})
    identity = response.headers['X-Answer-ID']
    monkeypatch.setattr(config, 'settings', replace(config.settings, database='other-database'))
    assert client.get('/chats', headers=HEADERS).json() == []
    assert client.get('/chats/' + chat, headers=HEADERS).status_code == 404
    assert client.delete('/chats/' + chat, headers=HEADERS).status_code == 404
    assert client.get(f'/export/{identity}/csv', headers=HEADERS).status_code == 404
    assert client.post('/ask', headers=HEADERS, json={'question': 'q', 'chat_id': chat}).json()['error']


def test_chat_routes_require_local_authentication(client):
    for method, path in [('get', '/chats'), ('post', '/chats'), ('get', '/chats/anything'), ('delete', '/chats/anything')]:
        assert getattr(client, method)(path).status_code == 401


def test_unconfigured_install_cannot_read_another_profiles_history(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', None)
    assert client.get('/chats', headers=HEADERS).status_code == 409


def test_followup_cannot_be_saved_as_a_context_free_training_example(client):
    chat = client.post('/chats', headers=HEADERS).json()['id']
    for question in ['میانگین دما؟', 'حالا دیروز؟']:
        result = client.post('/ask', headers=HEADERS, json={'question': question, 'chat_id': chat})
    identity = result.headers['X-Answer-ID']
    feedback = client.post(f'/feedback/{identity}/positive', headers=HEADERS).json()
    assert not feedback['ok'] and 'مستقل' in feedback['message']


def test_save_failure_is_reported_instead_of_claiming_the_answer_was_saved(client, monkeypatch):
    from rasam.core.chat_store import Stored
    chat = client.post('/chats', headers=HEADERS).json()['id']
    monkeypatch.setattr(client.app.state.session.chats, 'append',
                        lambda *args: Stored(reason='ذخیرهٔ گفتگو ممکن نشد.'))
    result = client.post('/ask', headers=HEADERS, json={'question': 'q', 'chat_id': chat}).json()
    assert result['error'] == 'ذخیرهٔ گفتگو ممکن نشد.'
    assert client.get('/chats/' + chat, headers=HEADERS).json()['turns'] == []
