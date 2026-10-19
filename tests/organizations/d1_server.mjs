import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { Miniflare, Log, LogLevel, convertV4MiniflareOptions } from '../../gateway/node_modules/miniflare/dist/src/index.js';
import { handle } from '../../organization_portal/cloudflare/worker.js';

// پایگاه D1 این فرایند مستقل و موقت است؛ دادهٔ سرویس‌های منتشرشده خوانده نمی‌شود.
const mf = new Miniflare(convertV4MiniflareOptions({ modules: true,
  script: 'export default { fetch() { return new Response("test"); } }',
  d1Databases: ['DB'], log: new Log(LogLevel.NONE) }));
const database = await mf.getD1Database('DB');
const source = await readFile(new URL('../../organization_portal/schema.sql', import.meta.url), 'utf8');
for (const statement of source.split(';').filter(value => value.trim())) await database.prepare(statement).run();
const server = http.createServer(async (req, res) => {
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const request = new Request('https://test.example.invalid' + req.url, {
      method: req.method, headers: req.headers, body: Buffer.concat(chunks)
    });
    const response = await handle(request, { DB: database, STORAGE_KEY: process.env.RASAM_TEST_STORAGE_KEY });
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch {
    res.writeHead(500).end('test bridge failed');
  }
});
server.listen(0, '127.0.0.1', () => process.stdout.write(JSON.stringify({ port: server.address().port }) + '\n'));
process.on('SIGTERM', async () => { server.close(); await mf.dispose(); process.exit(); });
