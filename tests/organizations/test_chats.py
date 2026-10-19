"""مالکیت، تکرار درخواست و سهمیه با چند دستگاه و درخواست هم‌زمان سنجیده می‌شوند."""

from concurrent.futures import ThreadPoolExecutor
import json
import secrets

import pytest

from organization_portal import usage
from organization_portal.chats import Chats
from organization_portal.connections import Connections
from organization_portal.errors import PortalError
from organization_portal.store import LocalStore


def ask(workspace, user="member", chat=None, request=None):
    chats = workspace["chats"]
    principal = workspace["users"][user]
    chat = chat or chats.create(principal, "one")["id"]
    return chats.ask(principal, "one", chat, request or secrets.token_hex(16), "سؤال آزمایشی")


def test_same_account_reads_saved_chat_from_another_instance(workspace):
    principal = workspace["users"]["member"]
    chat = workspace["chats"].create(principal, "one")["id"]
    answer = ask(workspace, chat=chat)
    other_store = LocalStore(workspace["store"].path)
    other_connections = Connections(other_store, workspace["key"], workspace["engine"], local=True)
    other_device = Chats(other_store, other_connections)
    saved = other_device.read(principal, "one", chat)
    assert saved["turns"][0]["id"] == answer["id"]
    assert saved["turns"][0]["answer"] == answer["answer"]


@pytest.mark.parametrize("user,org", [("other", "one"), ("admin", "one"), ("outside", "two")])
def test_other_member_or_manager_cannot_read_private_chat_by_id(workspace, user, org):
    owner = workspace["users"]["member"]
    chat = workspace["chats"].create(owner, "one")["id"]
    ask(workspace, chat=chat)
    with pytest.raises(PortalError) as error:
        workspace["chats"].read(workspace["users"][user], org, chat)
    assert error.value.status == 404


def test_repeated_request_returns_original_answer_without_running_or_charging_again(workspace):
    user = workspace["users"]["member"]
    chat = workspace["chats"].create(user, "one")["id"]
    request = secrets.token_hex(16)
    first = ask(workspace, chat=chat, request=request)
    second = ask(workspace, chat=chat, request=request)
    assert first["answer"] == second["answer"] and second["reused"]
    calls = [job for job in workspace["engine"].calls if job["mode"] == "answer"]
    assert len(calls) == 1
    assert usage.summary(workspace["store"], "one", user["id"])["member"]["used"] == 1


def test_model_or_network_failure_releases_reservation(workspace):
    workspace["engine"].failure = True
    answer = ask(workspace)
    summary = usage.summary(workspace["store"], "one", workspace["users"]["member"]["id"])
    assert answer["answer"]["error"]
    assert summary["member"] == {"used": 0, "reserved": 0}


@pytest.mark.parametrize("policy,used", [("valid_answer", 1), ("complete_answer", 0)])
def test_optional_result_policy_is_explicit(workspace, policy, used):
    workspace["engine"].complete = False
    workspace["chats"].quota_policy = policy
    ask(workspace)
    summary = usage.summary(workspace["store"], "one", workspace["users"]["member"]["id"])
    assert summary["member"] == {"used": used, "reserved": 0}


def test_parallel_devices_cannot_exceed_member_daily_limit(workspace):
    workspace["store"].query("UPDATE memberships SET daily_limit=1 WHERE id='member'")
    principal = workspace["users"]["member"]
    first = workspace["chats"].create(principal, "one")["id"]
    second = workspace["chats"].create(principal, "one")["id"]

    def attempt(chat):
        try:
            ask(workspace, chat=chat)
            return True
        except PortalError as error:
            assert error.status == 429
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [first, second]))
    assert results.count(True) == 1
    assert usage.summary(workspace["store"], "one", principal["id"])["member"]["used"] == 1


def test_revoking_permission_hides_history_and_drops_inflight_result(workspace):
    user = workspace["users"]["member"]
    chat = workspace["chats"].create(user, "one")["id"]

    def revoke():
        workspace["store"].query("UPDATE memberships SET allowed_sources=? WHERE id='member'", json.dumps(["private"]))

    workspace["engine"].on_answer = revoke
    with pytest.raises(PortalError):
        ask(workspace, chat=chat)
    assert workspace["chats"].listing(user, "one") == []
    summary = usage.summary(workspace["store"], "one", user["id"])
    assert summary["member"] == {"used": 0, "reserved": 0}
    assert "پاسخ ساختگی" not in str(workspace["store"].query("SELECT answer FROM turns"))


def test_expired_reservation_recovers_after_process_restart(workspace):
    user = workspace["users"]["member"]
    chat = workspace["chats"].create(user, "one")["id"]
    _, member, _ = workspace["chats"].owned(user, "one", chat)
    reservation = usage.reserve(workspace["store"], member, chat, secrets.token_hex(16), "قطع برنامه")
    workspace["store"].query("UPDATE reservations SET expires=0 WHERE id=?", reservation)
    usage.recover(workspace["store"])
    usage.recover(workspace["store"])
    assert usage.summary(workspace["store"], "one", user["id"])["member"] == {"used": 0, "reserved": 0}
    assert workspace["chats"].read(user, "one", chat)["busy_turn_id"] is None


def test_manager_sees_consumption_without_needing_chat_visibility(workspace):
    from organization_portal.organizations import members
    ask(workspace)
    rows = members(workspace['store'], workspace['users']['admin'], 'one')
    member = next(row for row in rows if row['id'] == 'member')
    assert member['used'] == 1 and member['reserved'] == 0
    assert 'answer' not in member


def test_oversized_result_returns_same_error_as_saved_history_and_refunds(workspace):
    workspace['engine'].run = lambda job: {'ok': True, 'complete': True,
        'answer': {'question': 'تست', 'message': 'x' * 900001}}
    user = workspace['users']['member']
    chat = workspace['chats'].create(user, 'one')['id']
    result = ask(workspace, chat=chat)
    saved = workspace['chats'].read(user, 'one', chat)['turns'][0]['answer']
    assert result['answer'] == saved and saved['error']
    assert usage.summary(workspace['store'], 'one', user['id'])['member'] == {'used': 0, 'reserved': 0}
