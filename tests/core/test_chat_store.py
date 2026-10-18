"""ذخیرهٔ محلی باید پس از راه‌اندازی دوباره بماند و از مرز مشتری عبور نکند."""

from datetime import datetime, timezone
from decimal import Decimal

from rasam.core.answer import Answer
from rasam.core.chat_store import ChatStore


def test_restart_preserves_complete_answer_and_exports(tmp_path):
    path = tmp_path / 'chats.sqlite3'
    store = ChatStore(path)
    chat = store.create('one').value
    answer = Answer('دمای دیروز؟', source='readings', query=[{'$limit': 1}],
                    rows=[{'n': Decimal('28.5'), 'at': datetime(2026, 1, 1, tzinfo=timezone.utc)}],
                    summary='دما ۲۸٫۵ بود.', chart={'chart_type': 'bar'})
    assert store.append('one', chat['id'], 'answer-one', answer).value
    restarted = ChatStore(path)
    assert restarted.list('one').value[0]['title'] == answer.question
    saved = restarted.read('one', chat['id']).value['turns'][0]
    assert saved['answer']['rows'][0]['n'] == 28.5
    assert saved['answer']['chart'] == answer.chart
    assert restarted.result('one', 'answer-one').value == saved['answer']


def test_other_customer_cannot_read_append_delete_or_export(tmp_path):
    store = ChatStore(tmp_path / 'chats.sqlite3')
    chat = store.create('one').value['id']
    assert store.append('one', chat, 'a', Answer('private', rows=[{'n': 42}])).value
    assert store.list('two').value == []
    assert store.read('two', chat).value is None
    assert not store.append('two', chat, 'b', Answer('other')).value
    assert not store.delete('two', chat).value
    assert store.result('two', 'a').value is None
    assert store.delete('one', chat).value
    assert store.result('one', 'a').value is None


def test_storage_error_is_a_clear_value(tmp_path):
    path = tmp_path / 'not-a-directory'
    path.write_text('blocked')
    result = ChatStore(path / 'chat.sqlite3').create('one')
    assert not result.ok and 'ذخیره' in result.reason
