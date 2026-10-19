"""قابلیت مشاهدهٔ گفتگو فقط از طرف مدیر کل داده می‌شود و لغوش فوراً اثر دارد."""

import secrets

import pytest

from organization_portal import managed_chats, organizations
from organization_portal.errors import PortalError


def platform(workspace):
    user = workspace["users"]["outside"]
    return {**user, "platform_admin": 1}


def test_manager_cannot_enable_own_chat_visibility(workspace):
    with pytest.raises(PortalError):
        organizations.configure(workspace["store"], workspace["users"]["admin"], "one", True, 100,
                                ["127.0.0.1"], True)
    with pytest.raises(PortalError):
        managed_chats.listing(workspace["store"], workspace["connections"], workspace["users"]["admin"], "one")


def test_platform_feature_allows_only_same_org_then_revocation_blocks_it(workspace):
    user = workspace["users"]["member"]
    chat = workspace["chats"].create(user, "one")["id"]
    workspace["chats"].ask(user, "one", chat, secrets.token_hex(16), "سؤال آزمایشی")
    organizations.configure(workspace["store"], platform(workspace), "one", True, 100, ["127.0.0.1"], True)
    manager = workspace["users"]["admin"]
    assert managed_chats.listing(workspace["store"], workspace["connections"], manager, "one")[0]["id"] == chat
    result = managed_chats.read(workspace["store"], workspace["connections"], manager, "one", chat)
    assert result["read_only"] and len(result["turns"]) == 1
    assert workspace["store"].query("SELECT action FROM audit_events WHERE action='member_chat_viewed'")
    with pytest.raises(PortalError):
        managed_chats.read(workspace["store"], workspace["connections"], workspace["users"]["outside"], "two", chat)
    organizations.configure(workspace["store"], platform(workspace), "one", True, 100, ["127.0.0.1"], False)
    with pytest.raises(PortalError):
        managed_chats.read(workspace["store"], workspace["connections"], manager, "one", chat)
