#!/usr/bin/env node
/**
 * Multi-turn WebSocket test — tests TTL, compaction, and persistent plugin state.
 * Usage: node ws-multi-test.mjs [sessionKey]
 */

import WebSocket from "ws";
import crypto from "crypto";

const PORT = 18790;
const TOKEN = "test-env-token-resonantos-dev-2026";
const SESSION = process.argv[2] || `agent:main:multi-${Date.now()}`;

const MESSAGES = [
  "Tell me about FIFO eviction in R-Memory.",
  "How does the compression system work?",
  "What about the plugin hooks in OpenClaw?",
  "Now tell me about the weather today.",  // No SSoT keywords — should keep previous injections active
  "What is the SSoT hierarchy system?",
  "Tell me a joke.",  // Totally off-topic — tests TTL decay
];

let ws;
let msgId = 0;
const pending = new Map();
let currentMsg = 0;

function request(method, params = {}) {
  const id = `req-${++msgId}`;
  const payload = { type: "req", id, method, params };
  ws.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error(`timeout: ${method}`)); } }, 60000);
  });
}

function sendNextMessage() {
  if (currentMsg >= MESSAGES.length) {
    console.log("\n\n🏁 All messages sent. Checking gateway logs...");
    setTimeout(async () => {
      ws.close();
      // Read plugin logs
      const { execSync } = await import("child_process");
      const logs = execSync("grep -i 'resonantos\\|inject\\|keyword\\|expired\\|ttl' /tmp/test-gateway.log | tail -40").toString();
      console.log("\n📋 Plugin logs:\n" + logs);
      process.exit(0);
    }, 2000);
    return;
  }
  
  const msg = MESSAGES[currentMsg];
  console.log(`\n\n━━━ Turn ${currentMsg + 1}/${MESSAGES.length} ━━━`);
  console.log(`📤 "${msg}"`);
  
  request("chat.send", {
    sessionKey: SESSION,
    message: msg,
    deliver: false,
    idempotencyKey: crypto.randomUUID(),
  }).then(r => {
    console.log(`✓ Acked: ${r?.status}`);
  }).catch(e => {
    console.error(`✗ Error: ${e.message}`);
  });
}

ws = new WebSocket(`ws://127.0.0.1:${PORT}`, {
  origin: `http://127.0.0.1:${PORT}`,
  headers: { Origin: `http://127.0.0.1:${PORT}` },
});

ws.on("open", () => console.log("✓ Connected"));

ws.on("message", (data) => {
  const msg = JSON.parse(data.toString());
  
  if (msg.type === "res") {
    const h = pending.get(msg.id);
    if (h) { pending.delete(msg.id); msg.ok ? h.resolve(msg.payload) : h.reject(new Error(msg.error?.message || "fail")); }
    return;
  }
  
  if (msg.type === "event") {
    const { event, payload } = msg;
    
    if (event === "connect.challenge") {
      request("connect", {
        minProtocol: 3, maxProtocol: 3,
        client: { id: "webchat", version: "0.1.0", platform: "node", mode: "webchat", instanceId: crypto.randomUUID() },
        role: "operator", scopes: [], caps: [],
        auth: { token: TOKEN },
      }).then(() => {
        console.log("✓ Authenticated");
        console.log(`📋 Session: ${SESSION}\n`);
        sendNextMessage();
      }).catch(e => { console.error("✗ Auth failed:", e.message); ws.close(); });
      return;
    }
    
    // On final response, send next message
    if (event === "chat" && payload?.state === "final") {
      const text = typeof payload?.message === "string" ? payload.message : 
        (payload?.message?.content?.[0]?.text || JSON.stringify(payload?.message).slice(0, 300));
      console.log(`✅ Response: ${text?.slice(0, 200)}...`);
      currentMsg++;
      setTimeout(sendNextMessage, 500); // Small delay between turns
      return;
    }
    
    // Skip streaming noise
    if (event === "agent" && payload?.stream === "assistant") return;
    if (event === "chat" && payload?.state === "delta") return;
    if (event === "tick" || event === "health") return;
    
    if (event === "chat" && payload?.state === "error") {
      console.log(`❌ Error: ${payload?.errorMessage}`);
      currentMsg++;
      setTimeout(sendNextMessage, 500);
    }
  }
});

ws.on("error", (err) => console.error("✗ WS error:", err.message));
ws.on("close", (code) => { console.log(`\n✗ Closed: ${code}`); process.exit(0); });
setTimeout(() => { console.log("\n⏱ Timeout"); ws.close(); process.exit(1); }, 300000);
