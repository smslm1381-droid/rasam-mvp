"""خطاهای اتصال و تضمین ذخیرهٔ راز فقط پس از آزمایش موفق."""

from dataclasses import asdict
import socket
from urllib.parse import urlsplit, unquote

import pytest
import pymysql
from pymongo.errors import OperationFailure
from fastapi.testclient import TestClient

from rasam import vault
from rasam.core.connection_setup import ConnectionSetup
from rasam.databases import connectivity, registry
from rasam.databases.mongodb import connecting as mongo
from rasam.databases.mysql import connecting as mysql
from rasam.desktop.app import create_app


@pytest.mark.parametrize("db_type,port", [("mongodb", 27017), ("mysql", 3306)])
def test_form_builds_escaped_uri_and_metadata(db_type, port):
    agent = registry.AGENTS[db_type]
    uri = agent.build_connection_uri({"host": "::1", "username": "a@b", "password": "x:/@?#",
                                      "database": "data", "port": str(port)})
    parsed = urlsplit(uri)
    assert parsed.hostname == "::1" and parsed.port == port
    assert unquote(parsed.username) == "a@b" and unquote(parsed.password) == "x:/@?#"
    assert {field["name"] for field in agent.connection_fields()} == {
        "host", "port", "username", "password", "database"}


@pytest.mark.parametrize("error,category", [(socket.gaierror(), "host"),
    (ConnectionRefusedError(), "port"), (TimeoutError(), "timeout")])
def test_network_failures_are_distinct_and_do_not_echo_details(monkeypatch, error, category):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(connectivity.socket, "create_connection", fail)
    result = connectivity.preflight("mysql://user:secret@host/db", 3306)
    assert result.category == category and not result.ok
    assert "secret" not in result.message


@pytest.mark.parametrize("code,category", [(1045, "credentials"), (1049, "database"), (2013, "timeout")])
def test_mysql_classifies_driver_codes_without_raw_message(monkeypatch, code, category):
    monkeypatch.setattr(connectivity, "preflight", lambda *args: None)
    def fail(*args, **kwargs):
        raise pymysql.OperationalError(code, "password=secret-driver")
    monkeypatch.setattr(mysql.connection, "connect", fail)
    result = mysql.test_connection("mysql://u:p@localhost/db", "db")
    assert result.category == category and "secret-driver" not in result.message


def test_mongo_authentication_failure_is_safe(monkeypatch):
    monkeypatch.setattr(connectivity, "preflight", lambda *args: None)
    def fail(*args, **kwargs):
        raise OperationFailure("password=secret-driver", code=18)
    monkeypatch.setattr(mongo, "MongoClient", fail)
    result = mongo.test_connection("mongodb://u:p@localhost/db", "db")
    assert result.category == "credentials" and "secret-driver" not in result.message


def test_only_a_successful_probe_saves_the_secret(monkeypatch):
    saved = {}
    monkeypatch.setattr(vault, "write_secret", lambda key, value: (saved.update({key: value}) or vault.Result(True)))
    setup = ConnectionSetup()
    agent = registry.AGENTS["mysql"]
    monkeypatch.setattr(agent, "test_connection", lambda *args: connectivity.report("credentials"))
    assert not setup.test("mysql", {"database": "db"}, "mysql://u:p@localhost/db")["ok"]
    assert saved == {} and setup.pending is None
    monkeypatch.setattr(agent, "test_connection", lambda *args: connectivity.report("connected"))
    result = setup.test("mysql", {"database": "db"}, "mysql://u:p@localhost/db")
    assert result["ok"] and len(saved) == 1
    assert "mysql://" not in str(setup.pending) and "mysql://" not in str(result)


def test_vault_failure_does_not_activate_the_connection(monkeypatch):
    monkeypatch.setattr(registry.AGENTS["mysql"], "test_connection", lambda *args: connectivity.report("connected"))
    monkeypatch.setattr(vault, "write_secret", lambda *args: vault.Result(False, error="انبار امن در دسترس نیست"))
    setup = ConnectionSetup()
    assert setup.test("mysql", {"database": "db"}, "mysql://u:p@localhost/db")["category"] == "vault"
    assert setup.pending is None


def test_setup_routes_require_token_and_never_echo_input(monkeypatch):
    client = TestClient(create_app("token"), base_url="http://127.0.0.1", client=("127.0.0.1", 1))
    assert client.get("/setup/databases").status_code == 401
    headers = {"X-Rasam-Token": "token"}
    assert len(client.get("/setup/databases", headers=headers).json()) == 2
    response = client.post("/setup/test", headers=headers,
                           json={"db_type": "missing", "values": {"password": "private"}})
    assert response.status_code == 200 and not response.json()["ok"]
    assert "private" not in response.text
