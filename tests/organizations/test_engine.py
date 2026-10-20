"""مسیر فرایند جدا و تعریف پاسخ کامل بدون سرویس مدل بررسی می‌شوند."""

import base64
import os
from pathlib import Path

import pytest
import yaml

from organization_portal.engine import Engine
from organization_portal.engine_worker import outcome, prepare
from organization_portal.errors import PortalError
from organization_portal.settings import Settings
from rasam.core.answer import Answer


@pytest.mark.parametrize('kind', ['csv', 'excel'])
def test_actual_subprocess_exports_without_model(kind, monkeypatch):
    monkeypatch.setenv('RASAM_LLM_API_KEY', 'must-not-be-used')
    result = Engine(local=True).run({'mode': 'export', 'kind': kind, 'rows': [{'name': '=1+1', 'value': 25}]})
    assert result['ok']
    content = base64.b64decode(result['content'])
    assert content.startswith(b'PK') if kind == 'excel' else b'25' in content


def test_profile_is_request_scoped_and_uses_only_explicit_model_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    for name in ['API_KEY', 'BASE_URL', 'MODEL']:
        monkeypatch.delenv('RASAM_ORG_LLM_' + name, raising=False)
        monkeypatch.setenv('RASAM_LLM_' + name, 'personal-must-not-be-used')
    job = {'db_type': 'mysql', 'uri': 'mysql://reader:test@127.0.0.1/data?tls=true',
           'allowed_hosts': ['127.0.0.1'], 'database': 'data', 'local': True, 'sources': ['readings']}
    prepare(tmp_path, job)
    profile = yaml.safe_load((tmp_path / 'customers/organization/profile.yaml').read_text())
    assert profile['allowed_sources'] == ['readings']
    assert profile['limits']['max_rows'] == 1000
    assert os.environ['RASAM_LLM_API_KEY'] == 'not-configured'


@pytest.mark.parametrize('changes,complete', [({}, True), ({'summary': None}, False),
    ({'chart': None}, False), ({'error': 'خطای تست'}, False)])
def test_every_requested_part_must_succeed(changes, complete):
    values = dict(question='نمودار دما را نشان بده', source='readings', query='SELECT value FROM readings',
                  rows=[{'value': 25}], summary='پاسخ تست', chart={'chart_type': 'bar'})
    result = outcome(Answer(**(values | changes)))
    assert result['complete'] is complete


def test_incomplete_quota_policy_is_rejected(workspace, tmp_path):
    with pytest.raises(PortalError):
        Settings(tmp_path, 'http://127.0.0.1:8795', workspace['key'], local=True,
                 quota_policy='valid_answer').validate()


def test_cloudflare_migration_matches_local_schema():
    root = Path(__file__).resolve().parents[2] / 'organization_portal'
    assert (root / 'schema.sql').read_bytes() == (root / 'cloudflare/migrations/0001_organizations.sql').read_bytes()
