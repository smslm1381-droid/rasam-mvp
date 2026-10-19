import release from "./release.json" with { type: "json" };

async function readObject(env, method) {
  if (!env.RELEASES) return null;
  try {
    return await env.RELEASES[method](release.objectKey);
  } catch {
    return null;
  }
}

async function plansResponse(request, env) {
  try {
    const url = new URL(env.CATALOG_URL);
    if (url.protocol !== "https:" || url.username || url.password) throw new Error("invalid catalog");
    const response = await env.CATALOG.fetch(url.href, { signal: AbortSignal.timeout(5000), redirect: "manual" });
    if (!response.ok) throw new Error("catalog unavailable");
    const text = await response.text();
    if (text.length > 100000) throw new Error("large catalog");
    const data = JSON.parse(text);
    if (!Array.isArray(data.plans)) throw new Error("invalid catalog");
    // فعال‌شدن پرداخت نیاز به مسیر واقعی و بررسی سروری دارد؛ پرچم عمومی کافی نیست.
    const body = JSON.stringify({ plans: data.plans, currency: "تومان", payment_enabled: false });
    return new Response(request.method === "HEAD" ? null : body, {
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ error: "اطلاعات پلن‌ها اکنون در دسترس نیست." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

// فقط فایل نسخهٔ منتشرشده قابل دریافت است؛ کلید دلخواه از کاربر نمی‌گیریم.
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path !== "/plans.json" && path !== "/release.json" && !path.startsWith("/downloads/")) {
      return env.ASSETS.fetch(request);
    }
    if (!["GET", "HEAD"].includes(request.method)) {
      return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
    }
    if (path === "/plans.json") return plansResponse(request, env);
    if (path === "/release.json") {
      const object = await readObject(env, "head");
      return Response.json({ ...release, available: Boolean(object) }, {
        headers: { "Cache-Control": "no-store" },
      });
    }
    if (path !== release.downloadPath) return new Response(null, { status: 404 });
    const object = await readObject(env, request.method === "HEAD" ? "head" : "get");
    if (!object) return new Response("فایل نصب در دسترس نیست.", { status: 503 });
    return new Response(request.method === "HEAD" ? null : object.body, {
      headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": `attachment; filename="${release.filename}"`,
        "Content-Length": String(object.size),
        "ETag": object.httpEtag,
        "Cache-Control": "public, max-age=86400, immutable",
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
};
