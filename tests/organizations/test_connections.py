"""رمز سمت سرور محصور است و مقصد یا فایل دلخواه از مرورگر پذیرفته نمی‌شود."""

from unittest.mock import Mock

import pytest

from organization_portal import network
from organization_portal.errors import PortalError


def test_only_org_manager_can_configure_shared_connection_and_no_password_is_returned(workspace):
    connection = workspace["connections"]
    with pytest.raises(PortalError):
        connection.save(workspace["users"]["member"], "one", workspace["data"])
    public = connection.public(workspace["users"]["admin"], "one")
    assert "private-test-db-password" not in str(public)
    assert "private-test-db-password" not in str(workspace["store"].query("SELECT * FROM connections"))


def test_question_job_only_receives_members_allowed_tables(workspace):
    _, job, _ = workspace["connections"].authorized(workspace["users"]["member"], "one")
    assert job["sources"] == ["readings"]
    assert "tls=true" in job["uri"]


@pytest.mark.parametrize("db_type,uri", [
    ("mysql", "mysql://u:p@db/data?tls=false"),
    ("mysql", "mysql://u:p@db/data?ssl_ca=/etc/passwd"),
    ("mongodb", "mongodb://u:p@db/data?tlsAllowInvalidCertificates=true"),
    ("mongodb", "mongodb://u:p@db/data?tlsCAFile=/etc/passwd"),
    ("mongodb", "mongodb://u:p@db/data?tls=true&tls=false"),
])
def test_unsafe_connection_options_cannot_be_saved(db_type, uri):
    with pytest.raises(PortalError):
        network.secure_uri(db_type, uri)


def test_destination_must_be_approved_before_dns_lookup(monkeypatch):
    dns = Mock()
    monkeypatch.setattr(network.socket, "getaddrinfo", dns)
    with pytest.raises(PortalError):
        network.check_destination("mysql://u:p@unapproved.invalid/data?tls=true", ["approved.invalid"])
    dns.assert_not_called()


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "::1", "0.0.0.0"])
def test_hosted_service_cannot_connect_to_host_or_metadata_services(monkeypatch, address):
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *a, **kw: [(None, None, None, None, (address, 3306))])
    with pytest.raises(PortalError):
        network.check_destination("mysql://u:p@approved.invalid/data?tls=true", ["approved.invalid"])


def test_srv_root_without_address_record_uses_verified_srv_targets(monkeypatch):
    import dns.resolver
    from types import SimpleNamespace
    monkeypatch.setattr(dns.resolver, 'resolve', lambda *a, **kw: [
        SimpleNamespace(target='node.cluster.example.invalid.', port=27017)])
    lookup = Mock(return_value=[(None, None, None, None, ('203.0.113.10', 27017))])
    monkeypatch.setattr(network.socket, 'getaddrinfo', lookup)
    network.check_destination('mongodb+srv://u:p@cluster.example.invalid/data?tls=true', ['cluster.example.invalid'])
    lookup.assert_called_once_with('node.cluster.example.invalid', 27017, type=network.socket.SOCK_STREAM)


def test_srv_target_cannot_route_to_metadata_service(monkeypatch):
    import dns.resolver
    from types import SimpleNamespace
    monkeypatch.setattr(dns.resolver, 'resolve', lambda *a, **kw: [
        SimpleNamespace(target='node.cluster.example.invalid.', port=27017)])
    monkeypatch.setattr(network.socket, 'getaddrinfo', lambda *a, **kw: [
        (None, None, None, None, ('169.254.169.254', 27017))])
    with pytest.raises(PortalError):
        network.check_destination('mongodb+srv://u:p@cluster.example.invalid/data?tls=true', ['cluster.example.invalid'])
