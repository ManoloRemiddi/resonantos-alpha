#!/usr/bin/env node
/**
 * WebSocket test client for OpenClaw test gateway.
 * Usage: node ws-test.mjs "message text" [sessionKey]
 */

import WebSocket from "ws";
import crypto from "crypto";

const PORT = 18790;
const TOKEN = "test-env-token-resonantos-dev-2026";
const SESSION = process.argv[3] || "agent:main:main";
const MESSAGE = process.argv[2] || "Hello from ws-test";

const ws = new WebSocket(`ws://127.0.0.1:${PORT}`, {
  origin: `http://127.0.0.1:${PORT}`,
  headers: { Origin: `http://127.0.0.1:${PORT}` },
});

let msgId = 0;
const pending = new Map();
let connectNonce = null;
let authenticated = false;

function request(method, params = {}) {
  const id = `req-${++msgId}`;
  const payload = { type: "req", id, method, params };
  console.log(`→ [${method}]`);
  ws.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id);
        reject(new Error(`timeout: ${method}`));
      }
    }, 30000);
  });
}

async function doConnect() {
  const params = {
    minProtocol: 3,
    maxProtocol: 3,
    client: {
      id: "webchat",
      version: "0.1.0",
      platform: "node",
      mode: "webchat",
      instanceId: crypto.randomUUID(),
    },
    role: "operator",
    scopes: [],
    caps: [],
    auth: { token: TOKEN },
  };
  // nonce is for device identity signing, skip for token-only auth
  
  const hello = await request("connect", params);
  console.log("✓ Authenticated");
  authenticated = true;
  
  // Send message
  console.log(`\n📤 Sending: "${MESSAGE}"`);
  const result = await request("chat.send", {
    sessionKey: SESSION,
    message: MESSAGE,
    deliver: false,
    idempotencyKey: crypto.randomUUID(),
  });
  console.log("✓ chat.send acked:", result?.status || "ok");
  console.log("⏳ Waiting for response...\n");
}

ws.on("open", () => {
  console.log("✓ Connected to test gateway on port " + PORT);
});

ws.on("message", (data) => {
  const msg = JSON.parse(data.toString());
  
  // Handle responses
  if (msg.type === "res") {
    const handler = pending.get(msg.id);
    if (handler) {
      pending.delete(msg.id);
      msg.ok ? handler.resolve(msg.payload) : handler.reject(new Error(msg.error?.message || "failed"));
    }
    return;
  }
  
  // Handle events
  if (msg.type === "event") {
    const { event, payload } = msg;
    
    // Challenge → connect
    if (event === "connect.challenge") {
      connectNonce = payload?.nonce;
      console.log("← [challenge] nonce received");
      doConnect().catch(e => {
        console.error("✗ Connect failed:", e.message);
        ws.close();
      });
      return;
    }
    
    // Chat events
    if (event === "chat") {
      const state = payload?.state;
      if (state === "delta") {
        process.stdout.write(".");
        return;
      }
      if (state === "final") {
        const content = typeof payload?.message === "string" 
          ? payload.message 
          : JSON.stringify(payload?.message)?.slice(0, 1000);
        console.log(`\n\n✅ [FINAL] Response:`);
        console.log(content?.slice(0, 1000));
        setTimeout(() => { ws.close(); process.exit(0); }, 1000);
        return;
      }
      if (state === "error") {
        console.log(`\n❌ [ERROR] ${payload?.errorMessage}`);
        setTimeout(() => { ws.close(); process.exit(1); }, 1000);
        return;
      }
      console.log(`← [chat:${state}]`, JSON.stringify(payload).slice(0, 200));
      return;
    }
    
    // Agent events (tool calls, etc.)
    if (event === "agent") {
      const kind = payload?.kind || payload?.type;
      console.log(`← [agent:${kind}]`, JSON.stringify(payload).slice(0, 200));
      return;
    }
    
    // Other events
    console.log(`← [${event}]`, JSON.stringify(payload).slice(0, 150));
  }
});

ws.on("error", (err) => console.error("✗ WS error:", err.message));
ws.on("close", (code, reason) => {
  console.log(`\n✗ Closed: ${code} ${reason}`);
  process.exit(code === 1000 ? 0 : 1);
});

setTimeout(() => { console.log("\n⏱ Timeout"); ws.close(); process.exit(1); }, 120000);
