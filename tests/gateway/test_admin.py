"""صدور بدون نگهداری کلید خام و ساخت امن دستور مدیریت D1."""

import pytest
from gateway import admin, licenses


@pytest.mark.parametrize("plan,days", [("monthly", 30), ("yearly", 365)])
def test_issued_key_is_random_and_only_its_hash_is_in_sql(plan, days):
    key, identifier, expiry, sql = admin.issue("customer", plan, now=1000)
    assert identifier == licenses.token_hash(key) and len(key) > 40
    assert key not in sql and identifier in sql
    assert expiry == 1000 + days * 86400
    assert ", 20)" in sql
    assert admin.issue("customer", plan, now=1000)[0] != key


def test_customer_name_is_a_sql_literal_and_quota_is_validated():
    key, identifier, expiry, sql = admin.issue("a'); DROP TABLE licenses; --", "monthly", 42)
    assert "'a''); DROP TABLE licenses; --'" in sql
    assert ", 42)" in sql
    with pytest.raises(ValueError):
        admin.issue("customer", "monthly", 0)


def test_extend_and_revoke_accept_only_public_hash_identifiers():
    identifier = "a" * 64
    assert "active = 0" in admin.change(identifier)
    assert "active = 1" in admin.change(identifier, days=30, now=100)
    assert "MAX(expires_at, 100) + 2592000" in admin.change(identifier, days=30, now=100)
    with pytest.raises(ValueError):
        admin.change("'; DROP TABLE licenses")
    with pytest.raises(ValueError):
        admin.change(identifier, days=-1)
