#!/usr/bin/env node
/**
 * R-Awareness Telegram Proxy
 * 
 * Intercepts Telegram webhooks, analyzes keywords, writes injection files,
 * then forwards to Clawdbot. This ensures R-Awareness sees the message
 * BEFORE Clawdbot's hooks fire.
 * 
 * Flow:
 * Telegram → Proxy (analyze + write) → Clawdbot (hook reads file)
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
  port: 18780,
  clawdbotPort: 18789,
  clawdbotHost: '127.0.0.1',
  pendingDir: path.join(os.homedir(), '.clawdbot/r-awareness/pending'),
  ssotRoots: [
    path.join(os.homedir(), 'clawd/agents/strategist'),
    path.join(os.homedir(), 'clawd/projects/resonantos/docs'),
    path.join(os.homedir(), 'clawd/projects/resonantos'),
  ],
  maxDocsPerMessage: 3,
  maxTokensPerDoc: 5000,
};

// ============================================================================
// Keyword Mappings
// ============================================================================

// Keyword → document paths (relative to ssotRoots)
const KEYWORD_DOCS = {
  // Memory system
  'memory': ['R-MEMORY_SPEC.md', 'docs/R-MEMORY_SPEC.md'],
  'r-memory': ['R-MEMORY_SPEC.md', 'docs/R-MEMORY_SPEC.md'],
  'awareness': ['R-AWARENESS_SPEC.md', 'docs/R-AWARENESS_SPEC.md'],
  'r-awareness': ['R-AWARENESS_SPEC.md', 'docs/R-AWARENESS_SPEC.md'],
  
  // Core architecture
  'architecture': ['ARCHITECTURE.md'],
  'logician': ['docs/LOGICIAN.md', 'logician/README.md'],
  'guardian': ['guardian/WATCHDOG_SPEC.md', 'docs/GUARDIAN_SPEC.md'],
  'shield': ['docs/SHIELD_SPEC.md'],
  
  // Projects
  'dao': ['docs/DAO_SPEC.md', 'reference/anthill-dao/README.md'],
  'resonantos': ['docs/RESONANTOS_SPEC.md', 'README.md'],
};

// Keyword → Logician rule reminders
const KEYWORD_RULES = {
  'delegate': `🔒 LOGICIAN: Delegation Required
strategist MUST delegate: code → coder | testing → tester | ui → designer | research → researcher`,

  'spawn': `🔒 LOGICIAN: Mission Brief Required
Include: WHY (problem) | WHAT (deliverables) | CONTEXT (bigger picture) | AGENCY (freedom to decide)`,

  'cron': `🔒 LOGICIAN: Cost Estimate Required
💰 Provide: Frequency | Agent (model) | Per-run tokens | Monthly cost
Opus: $15/M input, $75/M output | Base context: ~20k tokens`,

  'heartbeat': `🔒 LOGICIAN: Cost Estimate Required
Heartbeat = recurring automation. Provide frequency + token cost estimate.`,

  'buy': `🔒 LOGICIAN: Spending Approval Required
ANY financial transaction requires explicit approval. Threshold: $0`,

  'purchase': `🔒 LOGICIAN: Spending Approval Required
Purchases, subscriptions, payments require approval before committing.`,

  'subscribe': `🔒 LOGICIAN: Spending Approval Required`,

  'done': `🔒 LOGICIAN: Evidence Required
"Done/fixed/working" claims MUST include test evidence (screenshot, terminal output, health check).
Not valid: code review, "looks correct", assumptions.`,

  'fixed': `🔒 LOGICIAN: Evidence Required
"Fixed" claims require actual test evidence, not code analysis.`,

  'working': `🔒 LOGICIAN: Evidence Required
"Working" claims require test evidence.`,

  'install': `🔒 LOGICIAN: External Code Validation
ALL external code MUST be validated: security scan → sandbox test → approval`,

  'npm': `🔒 LOGICIAN: External Code Validation
npm packages require validation before installation.`,

  'pip': `🔒 LOGICIAN: External Code Validation
pip packages require validation before installation.`,

  'new protocol': `🔒 DEVELOPMENT PROTOCOL: Design-Level Work Detected
MANDATORY: Run self-debate (>=5 rounds) + deterministic audit BEFORE building.
Toolkit: Architect → Self-debate → Opportunity scan → Human perspective → Deterministic audit → Build → Verify
Compose freely. Log to memory/protocol-runs.jsonl. See PROTO-DEVELOPMENT.md`,

  'new architecture': `🔒 DEVELOPMENT PROTOCOL: Design-Level Work Detected
MANDATORY: Run self-debate (>=5 rounds) + deterministic audit BEFORE building.
See PROTO-DEVELOPMENT.md`,

  'new system': `🔒 DEVELOPMENT PROTOCOL: Design-Level Work Detected
MANDATORY: Run self-debate (>=5 rounds) + deterministic audit BEFORE building.
See PROTO-DEVELOPMENT.md`,

  'roadmap': `🔒 DEVELOPMENT PROTOCOL: Potential Design-Level Work
If this involves new architecture/protocol/system → run development toolkit.
If simple status check → no action needed.
See PROTO-DEVELOPMENT.md`,

  'overnight': `🔒 DEVELOPMENT PROTOCOL: Autonomous Work
Autonomous work on design-level items MUST use the development toolkit.
Run full toolkit. Present fortified result + "3 decisions needing human perspective."
See PROTO-DEVELOPMENT.md`,

  'research': `🔒 LOGICIAN: Researcher Protocol
Researcher = Perplexity PROXY. Spawn with: "Use Perplexity Advanced Research"
Token budget: ~2k. If >5k → protocol violation.`,

  'perplexity': `🔒 LOGICIAN: Researcher = Perplexity Proxy
Return raw Perplexity output, no independent analysis.`,

  'config': `🔒 LOGICIAN: Config Safety
Use gateway config.patch (not direct edit). Verify model exists before setting.`,

  'website': `🔒 LOGICIAN: Public Content Style
No em-dash (—). Punctuation OUTSIDE quotes. Verify source before describing features.`,

  'youtube': `🔒 LOGICIAN: Public Content Style
No em-dash. Punctuation outside quotes. Source verification required.`,

  'public': `🔒 LOGICIAN: Camouflage Enforcement
NEVER mention in public: Claude API, subscription workaround, ToS workaround.`,
};

// ============================================================================
// Utility Functions
// ============================================================================

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function findDocument(relativePath) {
  for (const root of CONFIG.ssotRoots) {
    const fullPath = path.join(root, relativePath);
    try {
      if (fs.existsSync(fullPath)) {
        const content = fs.readFileSync(fullPath, 'utf-8');
        const tokens = Math.ceil(content.length / 4);
        if (tokens <= CONFIG.maxTokensPerDoc) {
          return { path: fullPath, content, tokens };
        }
      }
    } catch (e) {
      // Continue to next root
    }
  }
  return null;
}

function extractKeywords(text) {
  if (!text) return { docs: [], rules: [] };
  
  const normalized = text.toLowerCase();
  const docs = [];
  const rules = [];
  
  for (const keyword of Object.keys(KEYWORD_DOCS)) {
    const regex = new RegExp(`\\b${keyword}\\b`, 'i');
    if (regex.test(normalized)) {
      docs.push(keyword);
    }
  }
  
  for (const keyword of Object.keys(KEYWORD_RULES)) {
    const regex = new RegExp(`\\b${keyword}\\b`, 'i');
    if (regex.test(normalized)) {
      rules.push(keyword);
    }
  }
  
  return {
    docs: [...new Set(docs)],
    rules: [...new Set(rules)],
  };
}

function extractMessageText(update) {
  // Handle various Telegram update types
  const message = update.message || update.edited_message || update.channel_post;
  if (!message) return '';
  
  // Text message
  if (message.text) return message.text;
  
  // Caption (for media)
  if (message.caption) return message.caption;
  
  // Voice/audio transcription might be in a custom field
  // Clawdbot handles transcription separately, so we might not see it here
  
  return '';
}

function extractSessionKey(update) {
  // Determine which agent/session this message is for
  // This depends on how Clawdbot routes messages
  const message = update.message || update.edited_message || update.channel_post;
  if (!message) return 'unknown';
  
  const chatId = message.chat?.id;
  // For now, use a simple mapping. In production, this would match Clawdbot's routing.
  // We'll use chat ID as a fallback session identifier
  return `telegram:${chatId}`;
}

function prepareInjection(text) {
  const { docs: docKeywords, rules: ruleKeywords } = extractKeywords(text);
  
  if (docKeywords.length === 0 && ruleKeywords.length === 0) {
    return null;
  }
  
  const injection = {
    timestamp: new Date().toISOString(),
    keywords: { docs: docKeywords, rules: ruleKeywords },
    documents: [],
    rules: [],
  };
  
  // Collect documents (limit to maxDocsPerMessage)
  let docCount = 0;
  for (const keyword of docKeywords) {
    if (docCount >= CONFIG.maxDocsPerMessage) break;
    
    const candidates = KEYWORD_DOCS[keyword] || [];
    for (const candidate of candidates) {
      const doc = findDocument(candidate);
      if (doc) {
        injection.documents.push({
          keyword,
          path: doc.path,
          content: doc.content,
          tokens: doc.tokens,
        });
        docCount++;
        break;
      }
    }
  }
  
  // Collect rules
  for (const keyword of ruleKeywords) {
    const rule = KEYWORD_RULES[keyword];
    if (rule) {
      injection.rules.push({ keyword, content: rule });
    }
  }
  
  return injection;
}

function writeInjectionFile(sessionKey, injection) {
  ensureDir(CONFIG.pendingDir);
  
  // Sanitize session key for filename
  const safeKey = sessionKey.replace(/[^a-zA-Z0-9_-]/g, '_');
  const filePath = path.join(CONFIG.pendingDir, `${safeKey}.json`);
  
  fs.writeFileSync(filePath, JSON.stringify(injection, null, 2));
  console.log(`[r-awareness] Wrote injection for ${sessionKey}: ${injection.documents.length} docs, ${injection.rules.length} rules`);
  
  return filePath;
}

// ============================================================================
// HTTP Proxy Server
// ============================================================================

const server = http.createServer((req, res) => {
  // Only handle POST requests (Telegram webhooks)
  if (req.method !== 'POST') {
    res.writeHead(200);
    res.end('R-Awareness Proxy OK');
    return;
  }
  
  let body = '';
  
  req.on('data', chunk => {
    body += chunk.toString();
  });
  
  req.on('end', () => {
    try {
      const update = JSON.parse(body);
      
      // Extract message text and analyze
      const text = extractMessageText(update);
      const sessionKey = extractSessionKey(update);
      
      console.log(`[r-awareness] Received update for ${sessionKey}: "${text.slice(0, 50)}..."`);
      
      // Prepare and write injection if keywords found
      if (text) {
        const injection = prepareInjection(text);
        if (injection) {
          writeInjectionFile(sessionKey, injection);
        }
      }
      
      // Forward to Clawdbot
      const options = {
        hostname: CONFIG.clawdbotHost,
        port: CONFIG.clawdbotPort,
        path: req.url,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
      };
      
      const proxyReq = http.request(options, proxyRes => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      });
      
      proxyReq.on('error', err => {
        console.error('[r-awareness] Proxy error:', err.message);
        res.writeHead(502);
        res.end('Proxy error');
      });
      
      proxyReq.write(body);
      proxyReq.end();
      
    } catch (err) {
      console.error('[r-awareness] Parse error:', err.message);
      res.writeHead(400);
      res.end('Invalid request');
    }
  });
});

// ============================================================================
// Start Server
// ============================================================================

ensureDir(CONFIG.pendingDir);

server.listen(CONFIG.port, '127.0.0.1', () => {
  console.log(`[r-awareness] Proxy listening on 127.0.0.1:${CONFIG.port}`);
  console.log(`[r-awareness] Forwarding to Clawdbot at ${CONFIG.clawdbotHost}:${CONFIG.clawdbotPort}`);
  console.log(`[r-awareness] Injection files: ${CONFIG.pendingDir}`);
});
