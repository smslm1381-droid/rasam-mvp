"""قیمت عمومی، تغییر فقط مدیریتی، و مدل/ظرفیت ثابت هر لایسنس روی D1 واقعی."""

import asyncio
from uuid import uuid4

import pytest

from gateway import licenses, products
from tests.gateway.test_panel import panel, sign_in


def body(**changes):
    return {"title": "پلن آزمایشی", "description": "توضیح", "model": "test/model-a",
            "daily_limit": 40, "monthly_price": 100000, "yearly_price": 900000,
            "published": True, **changes}


def product(db):
    identity = 'test-' + uuid4().hex
    asyncio.run(db.prepare("INSERT INTO products(id,title,daily_limit,position) VALUES (?,?,?,?)")
                .bind(identity, 'draft', 20, 9).run())
    return identity


def signed(panel):
    client, env = panel
    assert sign_in(client).status_code == 200
    return client, env, {'X-CSRF-Token': client.get('/api/me').json()['csrf']}


def test_only_published_complete_plans_are_public_and_payment_stays_disabled(panel):
    client, env = panel
    identity = product(env.DB)
    assert identity not in {p['id'] for p in client.get('/api/public/plans').json()['plans']}
    asyncio.run(products.save(env.DB, identity, body(), 'test-admin'))
    response = client.get('/api/public/plans')
    public = response.json()
    saved = next(p for p in public['plans'] if p['id'] == identity)
    assert saved['monthly_price'] == 100000 and saved['model'] == 'test/model-a'
    assert public['currency'] == 'تومان' and public['payment_enabled'] is False
    assert 'test-admin' not in response.text and 'token_hash' not in response.text


def test_plan_edits_require_authentication_origin_and_csrf(panel):
    client, env = panel
    identity = product(env.DB)
    assert client.get('/api/products').status_code == 401
    assert client.post('/api/products/'+identity, json=body()).status_code == 401
    client, env, headers = signed(panel)
    assert client.post('/api/products/'+identity, json=body()).status_code == 403
    assert client.post('/api/products/'+identity, json=body(), headers={**headers, 'Origin': 'https://evil.test'}).status_code == 403
    response = client.post('/api/products/'+identity, json=body(), headers=headers)
    assert response.status_code == 200 and response.json()['product']['daily_limit'] == 40
    changed = asyncio.run(env.DB.prepare('SELECT * FROM product_changes WHERE product_id=?').bind(identity).first())
    assert changed['actor'] == env.ADMIN_USERNAME


@pytest.mark.parametrize('changes', [dict(monthly_price=-1), dict(yearly_price=True), dict(daily_limit=0),
    dict(daily_limit=2.5), dict(model='https://bad?key=secret'), dict(model=''),
    dict(monthly_price=None, yearly_price=None), dict(published='yes')])
def test_invalid_or_incomplete_published_plan_is_rejected(changes):
    with pytest.raises(ValueError):
        products.validate(body(**changes))


def test_new_license_pins_model_quota_and_product_despite_later_price_edit(panel):
    client, env, headers = signed(panel)
    identity = product(env.DB)
    assert client.post('/api/products/'+identity, json=body(), headers=headers).status_code == 200
    request = {'customer': 'catalog-customer', 'plan': 'monthly', 'request_id': str(uuid4())}
    issued = client.post(f'/api/products/{identity}/issue', json=request, headers=headers)
    assert issued.status_code == 200
    key = issued.json()['key']
    status = asyncio.run(licenses.Licenses(env.DB).status(key))
    assert status['model'] == 'test/model-a' and status['daily_limit'] == 40
    reserved, reason = asyncio.run(licenses.Licenses(env.DB).reserve(key))
    assert not reason and reserved['model'] == 'test/model-a'
    assert client.post('/api/products/'+identity, json=body(model='test/model-b', daily_limit=80), headers=headers).status_code == 200
    current = asyncio.run(licenses.Licenses(env.DB).status(key))
    assert current['model'] == 'test/model-a' and current['daily_limit'] == 40
    row = asyncio.run(licenses.Licenses(env.DB).read(key))
    assert row['product_id'] == identity
    replayed = client.post(f'/api/products/{identity}/issue', json=request, headers=headers)
    assert replayed.status_code == 409


def test_unpublished_or_unoffered_period_cannot_issue_a_license(panel):
    client, env, headers = signed(panel)
    identity = product(env.DB)
    request = {'customer': 'test', 'plan': 'yearly', 'request_id': str(uuid4())}
    assert client.post(f'/api/products/{identity}/issue', json=request, headers=headers).status_code == 400
    client.post('/api/products/'+identity, json=body(yearly_price=None), headers=headers)
    assert client.post(f'/api/products/{identity}/issue', json=request, headers=headers).status_code == 400
