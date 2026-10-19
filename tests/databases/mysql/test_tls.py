"""گزینهٔ TLS نباید نادیده گرفته شود یا پیش از تشخیص نبود TLS رمز ارسال شود."""

import ssl
from unittest.mock import Mock

import pymysql
import pytest

from rasam.databases.mysql import connection, tls


def test_tls_requires_certificate_and_hostname_validation():
    options = connection.parse_uri("mysql://reader:private@db.example/data?tls=true")
    context = options["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


@pytest.mark.parametrize("query", ["tls=false&ssl_mode=VERIFY_IDENTITY", "tls=wrong",
    "ssl_mode=REQUIRED", "tls=true&tls=false", "tls=true&ssl_verify_identity=false",
    "tls=true&unknown=value", "tlsCAFile=file.pem", "tls=true&ssl_ca=a&tlsCAFile=b"])
def test_invalid_or_weak_tls_options_are_rejected(query):
    with pytest.raises(ValueError):
        connection.parse_uri("mysql://reader:private@db.example/data?" + query)


def test_missing_custom_ca_fails_without_attempting_a_network_connection(tmp_path, monkeypatch):
    connect = Mock()
    monkeypatch.setattr(connection.pymysql, "connect", connect)
    with pytest.raises(OSError):
        connection.connect("mysql://reader:private@db.example/data?tls=true&ssl_ca=" + str(tmp_path / "missing.pem"))
    connect.assert_not_called()


def test_server_without_tls_is_rejected_before_authentication(monkeypatch):
    authenticate = Mock()
    monkeypatch.setattr(pymysql.connections.Connection, "_request_authentication", authenticate)
    client = tls.VerifiedConnection(defer_connect=True, ssl=ssl.create_default_context())
    client.server_capabilities = 0
    with pytest.raises(pymysql.OperationalError) as error:
        client._request_authentication()
    assert error.value.args[0] == 2026
    authenticate.assert_not_called()


def test_tls_connection_uses_the_verified_connector(monkeypatch):
    connector = Mock()
    monkeypatch.setattr(tls, "VerifiedConnection", connector)
    connection.connect("mariadb://reader:private@db.example/data?ssl_mode=VERIFY_IDENTITY")
    assert connector.call_args.kwargs["ssl"].check_hostname
    assert connector.call_args.kwargs["client_flag"] == 0


def test_plain_local_connection_stays_compatible():
    options = connection.parse_uri("mysql://reader:private@localhost/data")
    assert "ssl" not in options
    assert options["database"] == "data"
