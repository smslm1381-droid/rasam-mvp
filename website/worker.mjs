import release from "./release.json" with { type: "json" };

async function readObject(env, method) {
  if (!env.RELEASES) return null;
  try {
    return await env.RELEASES[method](release.objectKey);
  } catch {
    return null;
  }
}

// فقط فایل نسخهٔ منتشرشده قابل دریافت است؛ کلید دلخواه از کاربر نمی‌گیریم.
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path !== "/release.json" && !path.startsWith("/downloads/")) {
      return env.ASSETS.fetch(request);
    }
    if (!["GET", "HEAD"].includes(request.method)) {
      return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
    }
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
