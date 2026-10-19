import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handle } from '../../organization_portal/cloudflare/worker.js';

const key = 'a-test-only-backend-secret-'.repeat(3);

test('the proxy adds its own secret and preserves the session cookie', async () => {
  let seen;
  const fetcher = async (url, options) => {
    seen = { url, options };
    return new Response('{"ok":true}', { headers: { 'Content-Type': 'application/json' } });
  };
  const request = new Request('https://workspace.example.invalid/api/auth/status', {
    headers: { Cookie: 'session=test', 'X-Rasam-Proxy-Key': 'injected-by-browser' }
  });
  const result = await handle(request, { BACKEND_URL: 'https://backend.example.invalid', BACKEND_KEY: key }, fetcher);
  assert.equal(result.status, 200);
  assert.equal(seen.options.headers.get('X-Rasam-Proxy-Key'), key);
  assert.equal(seen.options.headers.get('Cookie'), 'session=test');
  assert.equal(new URL(seen.url).origin, 'https://backend.example.invalid');
  assert.equal(result.headers.get('Cache-Control'), 'no-store');
});

test('a backend redirect never receives a follow-up with the service credential', async () => {
  const result = await handle(new Request('https://workspace.example.invalid/api/auth/status'), {
    BACKEND_URL: 'https://backend.example.invalid', BACKEND_KEY: key
  }, async (_, options) => {
    assert.equal(options.redirect, 'manual');
    return new Response(null, { status: 302, headers: { Location: 'https://another.invalid' } });
  });
  assert.equal(result.status, 502);
});

test('storage and other internal paths are not available to a browser', async () => {
  const result = await handle(new Request('https://workspace.example.invalid/internal/storage', { method: 'POST' }), { STORAGE_KEY: key });
  assert.equal(result.status, 403);
  const unknown = await handle(new Request('https://workspace.example.invalid/internal/other'), {});
  assert.equal(unknown.status, 404);
});

test('missing configuration is a clear failure, without returning a secret', async () => {
  const result = await handle(new Request('https://workspace.example.invalid/api/auth/status'), {});
  assert.equal(result.status, 503);
});
