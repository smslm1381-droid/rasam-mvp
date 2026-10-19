import { timingSafeEqual } from 'node:crypto';

// پل ذخیره‌سازی فقط سرور مورد اعتماد را می‌پذیرد؛ مرورگر هیچ کلید سرویس نمی‌گیرد.
function matches(actual, expected) {
  if (!expected || expected.length < 40 || typeof actual !== 'string') return false;
  const a = new TextEncoder().encode(actual);
  const b = new TextEncoder().encode(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function json(value, status = 200) {
  return Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } });
}

async function boundedBody(request) {
  if (!request.body) return null;
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 2 * 1024 * 1024) {
      await reader.cancel();
      throw new Error('body limit');
    }
    chunks.push(value);
  }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

async function storage(request, env) {
  if (request.method !== 'POST' || !env.STORAGE_KEY || env.STORAGE_KEY.length < 40
      || !matches(request.headers.get('Authorization'), 'Bearer ' + env.STORAGE_KEY)) {
    return json({ error: 'دسترسی مجاز نیست.' }, 403);
  }
  try {
    const body = JSON.parse(new TextDecoder().decode(await boundedBody(request)));
    if (!Array.isArray(body.statements) || !body.statements.length || body.statements.length > 50) throw new Error();
    const statements = body.statements.map(({ sql, params }) => {
      if (typeof sql !== 'string' || sql.length > 12000 || !/^\s*(SELECT|INSERT|UPDATE|DELETE)\b/i.test(sql)
          || sql.includes(';') || !Array.isArray(params) || params.length > 100) throw new Error();
      return env.DB.prepare(sql).bind(...params);
    });
    const results = await env.DB.batch(statements);
    return json({ results: results.map(item => ({ results: item.results || [], changes: item.meta?.changes || 0 })) });
  } catch (error) {
    const status = String(error?.message || '').includes('constraint') ? 409 : 503;
    return json({ error: 'ذخیره یا خواندن اطلاعات ممکن نشد.' }, status);
  }
}

async function proxy(request, env, fetcher) {
  if (!env.BACKEND_KEY || env.BACKEND_KEY.length < 40 || !env.BACKEND_URL) {
    return json({ detail: 'سرور سازمانی هنوز تنظیم نشده است.' }, 503);
  }
  const base = new URL(env.BACKEND_URL);
  if (base.protocol !== 'https:' || base.username || base.password) return json({ detail: 'تنظیم سرور معتبر نیست.' }, 503);
  const source = new URL(request.url);
  const destination = new URL(source.pathname + source.search, base.origin);
  const headers = new Headers(request.headers);
  for (const name of ['Authorization', 'Host', 'X-Rasam-Proxy-Key', 'X-Rasam-Client-IP']) headers.delete(name);
  headers.set('X-Rasam-Proxy-Key', env.BACKEND_KEY);
  headers.set('X-Rasam-Client-IP', request.headers.get('CF-Connecting-IP') || 'unknown');
  try {
    const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await boundedBody(request);
    const result = await fetcher(destination, { method: request.method, headers, body, redirect: 'manual' });
    if (result.status >= 300 && result.status < 400) return json({ detail: 'پاسخ سرور معتبر نیست.' }, 502);
    const response = new Response(result.body, result);
    response.headers.set('Cache-Control', 'no-store');
    return response;
  } catch {
    return json({ detail: 'سرور آزمایشی در حال آماده‌شدن یا خارج از دسترس است؛ کمی بعد دوباره تلاش کنید.' }, 503);
  }
}

export async function handle(request, env, fetcher = fetch) {
  const path = new URL(request.url).pathname;
  if (path === '/internal/storage') return storage(request, env);
  if (path.startsWith('/internal/')) return json({ error: 'پیدا نشد.' }, 404);
  if (path.startsWith('/api/')) return proxy(request, env, fetcher);
  return env.ASSETS.fetch(request);
}

export default { fetch: handle };
