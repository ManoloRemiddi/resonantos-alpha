#!/usr/bin/env node
/**
 * Test SSoT expiry notifications. TTL=3 so docs expire after 3 off-topic turns.
 */
import WebSocket from "ws";
import crypto from "crypto";

const PORT = 18790;
const TOKEN = "test-env-token-resonantos-dev-2026";
const SESSION = `agent:main:expiry-${Date.now()}`;

const MESSAGES = [
  "Tell me about FIFO eviction.",           // Turn 1: inject SSoTs
  "What's 2+2?",                            // Turn 2: off-topic
  "Tell me a joke.",                         // Turn 3: off-topic  
  "What color is the sky?",                  // Turn 4: off-topic — TTL=3 → should expire!
  "How are you today?",                      // Turn 5: confirm expiry notice was shown at turn 4
];

let ws, msgId = 0, currentMsg = 0;
const pending = new Map();

function request(method, params = {}) {
  const id = `req-${++msgId}`;
  ws.send(JSON.stringify({ type: "req", id, method, params }));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error(`timeout`)); } }, 60000);
  });
}

function sendNext() {
  if (currentMsg >= MESSAGES.length) {
    console.log("\n🏁 Done. Checking logs...");
    setTimeout(async () => {
      ws.close();
      const { execSync } = await import("child_process");
      const logs = execSync("grep -i 'inject\\|expir\\|expired' /tmp/test-gateway.log | tail -20").toString();
      console.log("\n📋 Injection/expiry logs:\n" + logs);
      process.exit(0);
    }, 2000);
    return;
  }
  const msg = MESSAGES[currentMsg];
  console.log(`\n━━━ Turn ${currentMsg + 1}/${MESSAGES.length}: "${msg}" ━━━`);
  request("chat.send", { sessionKey: SESSION, message: msg, deliver: false, idempotencyKey: crypto.randomUUID() })
    .catch(e => console.error("✗", e.message));
}

ws = new WebSocket(`ws://127.0.0.1:${PORT}`, { origin: `http://127.0.0.1:${PORT}`, headers: { Origin: `http://127.0.0.1:${PORT}` } });
ws.on("open", () => console.log("✓ Connected"));
ws.on("message", (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.type === "res") { const h = pending.get(msg.id); if (h) { pending.delete(msg.id); msg.ok ? h.resolve(msg.payload) : h.reject(new Error(msg.error?.message)); } return; }
  if (msg.type === "event") {
    if (msg.event === "connect.challenge") {
      request("connect", { minProtocol: 3, maxProtocol: 3, client: { id: "webchat", version: "0.1.0", platform: "node", mode: "webchat", instanceId: crypto.randomUUID() }, role: "operator", scopes: [], caps: [], auth: { token: TOKEN } })
        .then(() => { console.log("✓ Auth"); sendNext(); });
      return;
    }
    if (msg.event === "chat" && msg.payload?.state === "final") {
      const text = typeof msg.payload?.message === "string" ? msg.payload.message : msg.payload?.message?.content?.[0]?.text || "";
      const hasExpiry = text.includes("expired") || text.includes("⚠️") || text.includes("expir");
      console.log(`✅ Response (${text.length} chars)${hasExpiry ? " 🔔 EXPIRY NOTICE DETECTED" : ""}`);
      console.log(`   ${text.slice(0, 200)}...`);
      currentMsg++;
      setTimeout(sendNext, 300);
    }
  }
});
ws.on("error", (err) => console.error("✗", err.message));
ws.on("close", (code) => { console.log(`Closed: ${code}`); process.exit(0); });
setTimeout(() => { ws.close(); process.exit(1); }, 180000);
