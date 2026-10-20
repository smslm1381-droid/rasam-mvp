"""هویت بین دستگاه‌ها مشترک است؛ دعوت یا نام سازمان مجوز کاربران دیگر را نمی‌دهد."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from organization_portal import invitations, organizations
from organization_portal.auth import Accounts
from organization_portal.errors import PortalError
from organization_portal.permissions import membership
from organization_portal.store import LocalStore

PASSWORD = "only-a-test-password-123"


@pytest.fixture
def setup(tmp_path):
    store = LocalStore(tmp_path / "portal.sqlite3")
    accounts = Accounts(store)
    identity = accounts.create("platform@example.invalid", "مدیر رصام", PASSWORD, True)
    platform = store.query("SELECT id,email,name,platform_admin FROM users WHERE id=?", identity)[0]
    return store, accounts, platform


def make_org(setup, email="manager@example.invalid", name="سازمان اول"):
    store, accounts, platform = setup
    org = organizations.create(store, platform, name, email, ["db.example.invalid"], 100)
    invitations.accept(store, org["invitation"]["token"], "مدیر سازمان", PASSWORD, None)
    manager = accounts.current(accounts.login(email, PASSWORD, email))
    return org, manager


def test_two_devices_login_to_one_central_identity_and_email_is_unique(setup):
    store, accounts, _ = setup
    org, manager = make_org(setup)
    first = accounts.login("MANAGER@example.invalid", PASSWORD, "device-one")
    second = accounts.login("manager@example.invalid", PASSWORD, "device-two")
    assert accounts.current(first)["id"] == accounts.current(second)["id"] == manager["id"]
    with pytest.raises(PortalError) as error:
        accounts.create("MANAGER@example.invalid", "duplicate", PASSWORD)
    assert error.value.status == 409
    assert store.query("SELECT COUNT(*) AS n FROM users WHERE email=?", "manager@example.invalid")[0]["n"] == 1


def test_inviting_an_existing_user_requires_that_users_login(setup):
    store, accounts, platform = setup
    first, manager = make_org(setup)
    second = organizations.create(store, platform, "سازمان دوم", manager["email"], [], 100)
    token = second["invitation"]["token"]
    with pytest.raises(PortalError) as error:
        invitations.accept(store, token, "تصاحب", "a-new-test-password-123", None)
    assert error.value.status == 401
    invitations.accept(store, token, "ignored", "", manager)
    assert membership(store, manager, second["id"])["role"] == "admin"
    assert accounts.login(manager["email"], PASSWORD, "another-device")


def test_member_cannot_manage_or_select_another_organization(setup):
    store, accounts, _ = setup
    first, manager = make_org(setup)
    second, other = make_org(setup, "other@example.invalid", "سازمان دوم")
    invitation = organizations.invite(store, manager, first["id"], "member@example.invalid", "member", 5, [])
    invitations.accept(store, invitation["token"], "عضو", PASSWORD, None)
    member = accounts.current(accounts.login("member@example.invalid", PASSWORD, "member-device"))
    with pytest.raises(PortalError):
        organizations.members(store, member, first["id"])
    with pytest.raises(PortalError):
        organizations.members(store, manager, second["id"])
    assert membership(store, member, first["id"])["role"] == "member"


def test_invitation_is_single_use_under_concurrent_acceptance(setup):
    store, accounts, _ = setup
    first, manager = make_org(setup)
    invite = organizations.invite(store, manager, first["id"], "new@example.invalid", "member", 5, [])

    def accept():
        try:
            return invitations.accept(store, invite["token"], "عضو", PASSWORD, None)["ok"]
        except PortalError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(), range(2)))
    assert results.count(True) == 1
    assert len(store.query("SELECT id FROM users WHERE email=?", "new@example.invalid")) == 1


def test_disabled_membership_loses_access_and_other_organization_keeps_working(setup):
    store, accounts, _ = setup
    first, manager = make_org(setup)
    second, other = make_org(setup, "other@example.invalid", "سازمان دوم")
    invitation = organizations.invite(store, manager, first["id"], other["email"], "member", 5, [])
    invitations.accept(store, invitation["token"], "", "", other)
    member = membership(store, other, first["id"])
    organizations.update_member(store, manager, first["id"], member["id"], False, 5, [])
    with pytest.raises(PortalError):
        membership(store, other, first["id"])
    assert membership(store, other, second["id"])["role"] == "admin"


def test_password_and_session_are_not_stored_in_plaintext_and_logout_is_per_device(setup):
    store, accounts, _ = setup
    org, manager = make_org(setup)
    first = accounts.login(manager["email"], PASSWORD, "one")
    second = accounts.login(manager["email"], PASSWORD, "two")
    assert PASSWORD not in str(store.query("SELECT * FROM users"))
    assert first not in str(store.query("SELECT * FROM sessions"))
    accounts.logout(first)
    assert accounts.current(first) is None
    assert accounts.current(second)["id"] == manager["id"]


def test_login_is_rate_limited_and_changing_password_revokes_all_sessions(setup):
    store, accounts, _ = setup
    identity = accounts.create("limited@example.invalid", "عضو", PASSWORD)
    token = accounts.login("limited@example.invalid", PASSWORD, "valid-device")
    for _ in range(5):
        with pytest.raises(PortalError) as error:
            accounts.login("limited@example.invalid", "wrong-password", "bad-device")
    assert error.value.status == 429
    user = accounts.current(token)
    accounts.change_password(user, PASSWORD, "another-test-password-456")
    assert accounts.current(token) is None


def test_invite_cannot_grant_unapproved_tables_or_excess_quota(setup):
    store, accounts, _ = setup
    org, manager = make_org(setup)
    with pytest.raises(PortalError):
        organizations.invite(store, manager, org["id"], "member@example.invalid", "member", 5, ["private_table"])
    with pytest.raises(PortalError):
        organizations.invite(store, manager, org["id"], "member@example.invalid", "member", 101, [])
