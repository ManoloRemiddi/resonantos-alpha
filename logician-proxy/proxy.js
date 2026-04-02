const http = require('http');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');

const PROTO_PATH = path.join(__dirname, '..', 'logician', 'mangle-service', 'proto', 'mangle.proto');
const SOCK_ADDR = process.env.MANGLE_SOCK || '/tmp/mangle.sock';
const HTTP_PORT = parseInt(process.env.PORT || '8081', 10);

const packageDef = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true, longs: String, enums: String, defaults: true, oneofs: true,
});
const mangleProto = grpc.loadPackageDefinition(packageDef).mangle;

const client = new mangleProto.Mangle(
  `unix://${SOCK_ADDR}`, grpc.credentials.createInsecure()
);

function queryMangle(queryStr, program) {
  return new Promise((resolve, reject) => {
    const answers = [];
    const stream = client.Query({ query: queryStr, program: program || '' });
    stream.on('data', (answer) => answers.push(answer.answer));
    stream.on('end', () => resolve(answers));
    stream.on('error', (err) => {
      if (err.code === 5) resolve([]);
      else reject(err);
    });
  });
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => (data += chunk));
    req.on('end', () => {
      try { resolve(JSON.parse(data)); }
      catch (e) { reject(e); }
    });
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  
  try {
    if (req.url === '/health' && req.method === 'GET') {
      try {
        await queryMangle('agent(/main)');
        res.end(JSON.stringify({ ok: true, mangle: 'connected' }));
      } catch (err) {
        res.statusCode = 503;
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
      return;
    }

    if (req.method !== 'POST') {
      res.statusCode = 405;
      res.end(JSON.stringify({ error: 'Method not allowed' }));
      return;
    }

    const body = await parseBody(req);

    if (req.url === '/query') {
      const { predicate, args, query: rawQuery, program } = body;
      let q = rawQuery;
      if (!q && predicate) {
        const argList = args ? Object.values(args).map(v =>
          typeof v === 'string' ? `"${v}"` : String(v)
        ).join(', ') : 'X';
        q = `${predicate}(${argList})`;
      }
      if (!q) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'Missing query or predicate' }));
        return;
      }
      const answers = await queryMangle(q, program);
      res.end(JSON.stringify({ query: q, answers, count: answers.length }));
      return;
    }

    if (req.url === '/validate') {
      const { agentId, action, tool } = body;
      if (!agentId || !action) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'Missing agentId or action' }));
        return;
      }
      const trustAnswers = await queryMangle(`trust_level(/${agentId}, Level)`);
      const trustLevel = trustAnswers.length > 0 ? parseInt(trustAnswers[0].match(/\d+/)?.[0] || '0') : 0;
      let toolDangerous = false;
      if (tool) {
        const dangerousAnswers = await queryMangle(`dangerous_tool(/${tool})`);
        toolDangerous = dangerousAnswers.length > 0;
      }
      const blockAnswers = await queryMangle(`block_spawn(/${agentId}, Reason)`);
      const blocked = blockAnswers.length > 0;
      const blockReason = blocked ? blockAnswers[0] : null;
      const allowed = !blocked && (!toolDangerous || trustLevel >= 3);
      res.end(JSON.stringify({
        allowed, agentId, action, tool: tool || null,
        trustLevel, toolDangerous, blocked, blockReason,
      }));
      return;
    }

    if (req.url === '/agent_trust') {
      const { agentId } = body;
      if (!agentId) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'Missing agentId' }));
        return;
      }
      const answers = await queryMangle(`trust_level(/${agentId}, Level)`);
      const level = answers.length > 0 ? parseInt(answers[0].match(/\d+/)?.[0] || '0') : null;
      res.end(JSON.stringify({ agentId, level, raw: answers }));
      return;
    }

    if (req.url === '/dangerous_tool') {
      const { toolName } = body;
      if (!toolName) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'Missing toolName' }));
        return;
      }
      const answers = await queryMangle(`dangerous_tool(/${toolName})`);
      res.end(JSON.stringify({ toolName, isDangerous: answers.length > 0, raw: answers }));
      return;
    }

    res.statusCode = 404;
    res.end(JSON.stringify({ error: 'Unknown endpoint' }));
  } catch (err) {
    res.statusCode = 500;
    res.end(JSON.stringify({ error: err.message }));
  }
});

server.listen(HTTP_PORT, '127.0.0.1', () => {
  console.log(`Logician HTTP proxy listening on http://127.0.0.1:${HTTP_PORT}`);
  console.log(`Forwarding to gRPC at unix://${SOCK_ADDR}`);
});
