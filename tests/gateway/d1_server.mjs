import http from 'node:http';
import { Miniflare, Log, LogLevel, convertV4MiniflareOptions } from '../../gateway/node_modules/miniflare/dist/src/index.js';

// این پل فقط ابزار آزمون است؛ درگاه تصادفی و توکن فقط در حافظهٔ فرایند پدر می‌مانند.
const mf = new Miniflare(convertV4MiniflareOptions({ modules: true,
  script: 'export default { fetch() { return new Response("test"); } }',
  d1Databases: ['DB'], log: new Log(LogLevel.NONE) }));
const db = await mf.getD1Database('DB');
const server = http.createServer(async (req, res) => {
  if (req.headers.authorization !== process.env.RASAM_TEST_TOKEN) {
    res.writeHead(403).end(); return;
  }
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (input.method === 'batch') {
      const value = await db.batch(input.statements.map(item => db.prepare(item.sql).bind(...item.params)));
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(value));
      return;
    }
    const stmt = db.prepare(input.sql).bind(...input.params);
    const value = input.method === 'first' ? await stmt.first()
      : input.method === 'run' ? await stmt.run() : await stmt.all();
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(value));
  } catch {
    res.writeHead(500).end(JSON.stringify({ error: 'D1 query failed' }));
  }
});
server.listen(0, '127.0.0.1', () => process.stdout.write(JSON.stringify({ port: server.address().port }) + '\n'));
process.on('SIGTERM', async () => { server.close(); await mf.dispose(); process.exit(); });
