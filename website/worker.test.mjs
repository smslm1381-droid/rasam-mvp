import assert from "node:assert/strict";
import test from "node:test";
import worker from "./worker.mjs";
import release from "./release.json" with { type: "json" };

const request = (path, method = "GET") => new Request(`https://product.example${path}`, { method });

test("سایت از دارایی‌های عمومی پاسخ می‌دهد", async () => {
  const response = await worker.fetch(request("/"), { ASSETS: { fetch: () => new Response("site") } });
  assert.equal(await response.text(), "site");
});

test("تا بارگذاری واقعی فایل، دانلود فعال نیست", async () => {
  const response = await worker.fetch(request("/release.json"), {});
  assert.equal((await response.json()).available, false);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal((await worker.fetch(request(release.downloadPath), {})).status, 503);
});

test("وضعیت انتشار وجود واقعی فایل را می‌سنجد", async () => {
  const env = { RELEASES: { head: async key => {
    assert.equal(key, release.objectKey);
    return { size: release.size };
  } } };
  const response = await worker.fetch(request("/release.json"), env);
  assert.equal((await response.json()).available, true);
});

test("فایل دلخواه یا راز از مسیر دانلود خوانده نمی‌شود", async () => {
  const env = { RELEASES: { get: () => assert.fail("unexpected object lookup") } };
  assert.equal((await worker.fetch(request("/downloads/private.env"), env)).status, 404);
});

test("بارگذاری یا حذف عمومی فایل مجاز نیست", async () => {
  for (const method of ["POST", "PUT", "DELETE"]) {
    const response = await worker.fetch(request(release.downloadPath, method), {});
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("Allow"), "GET, HEAD");
  }
});

test("دانلود مستقیم، محتوا و نام فایل صحیح دارد", async () => {
  const env = { RELEASES: { get: async key => {
    assert.equal(key, release.objectKey);
    return { body: "installer", size: 9, httpEtag: '"sample"' };
  } } };
  const response = await worker.fetch(request(release.downloadPath), env);
  assert.equal(await response.text(), "installer");
  assert.equal(response.headers.get("Content-Length"), "9");
  assert.equal(response.headers.get("Content-Disposition"), `attachment; filename="${release.filename}"`);
  assert.equal(response.headers.get("X-Content-Type-Options"), "nosniff");
});

test("HEAD بدون خواندن بدنهٔ نصب‌کننده کار می‌کند", async () => {
  const env = { RELEASES: {
    head: async () => ({ size: 9, httpEtag: '"sample"' }),
    get: () => assert.fail("HEAD must not download installer"),
  } };
  const response = await worker.fetch(request(release.downloadPath, "HEAD"), env);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "");
});

test("قطع فضای ذخیره‌سازی، خطای خام را عمومی نمی‌کند", async () => {
  const env = { RELEASES: { get: async () => { throw new Error("private storage error"); } } };
  const response = await worker.fetch(request(release.downloadPath), env);
  assert.equal(response.status, 503);
  assert.doesNotMatch(await response.text(), /private storage error/);
});

test("پلن‌ها از نشانی تنظیم‌شده خوانده می‌شوند و هیچ درگاهی فعال نیست", async (t) => {
  const catalog = { fetch: async (url, options) => {
    assert.equal(options.redirect, "manual");
    assert.equal(String(url), 'https://admin.example/api/public/plans');
    return Response.json({ plans: [{ id: 'test', title: 'پلن', monthly_price: 10 }], payment_enabled: true });
  } };
  const response = await worker.fetch(request('/plans.json'), { CATALOG: catalog, CATALOG_URL: 'https://admin.example/api/public/plans' });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  const data = await response.json();
  assert.equal(data.plans[0].id, 'test');
  assert.equal(data.payment_enabled, false);
});

test("خرابی فهرست پلن خطای روشن می‌دهد و POST عمومی نمی‌پذیرد", async (t) => {
  const catalog = { fetch: async () => { throw new Error('private upstream error'); } };
  const response = await worker.fetch(request('/plans.json'), { CATALOG: catalog, CATALOG_URL: 'https://admin.example/plans' });
  assert.equal(response.status, 503);
  assert.doesNotMatch(await response.text(), /private/);
  assert.equal((await worker.fetch(request('/plans.json', 'POST'), {})).status, 405);
});
