"""درایور واقعی و گواهی آزمایشی استفاده می‌شوند؛ سرویس MySQL شبیه‌سازی شده است."""

import pymysql
import pytest
from urllib.parse import urlencode

from rasam.databases.mysql import connection
from tests.organizations.tls_mysql_server import server


def uri(port, ca=None):
    values = {"tls": "true"}
    if ca:
        values["ssl_ca"] = str(ca)
    return f"mysql://reader:test-password@localhost:{port}/data?" + urlencode(values)


def test_real_driver_accepts_trusted_certificate_and_matching_host(tmp_path):
    with server(tmp_path) as (port, ca, state):
        with connection.connect(uri(port, ca), read_timeout=3, write_timeout=3) as client:
            assert client._sock.cipher()
        assert state["tls_auth_received"] and not state["plaintext_auth_sent"]


def test_real_driver_rejects_wrong_certificate_hostname(tmp_path):
    with server(tmp_path, host="wrong.example.invalid") as (port, ca, state):
        with pytest.raises(pymysql.MySQLError):
            connection.connect(uri(port, ca), read_timeout=3, write_timeout=3)
        assert not state["tls_auth_received"]


def test_real_driver_rejects_unknown_ca(tmp_path):
    with server(tmp_path) as (port, ca, state):
        with pytest.raises(pymysql.MySQLError):
            connection.connect(uri(port), read_timeout=3, write_timeout=3)
        assert not state["tls_auth_received"]


def test_real_driver_does_not_send_password_when_server_has_no_tls(tmp_path):
    with server(tmp_path, tls_enabled=False) as (port, ca, state):
        with pytest.raises(pymysql.OperationalError) as error:
            connection.connect(uri(port, ca), read_timeout=3, write_timeout=3)
        assert error.value.args[0] == 2026
        assert not state["plaintext_auth_sent"]
