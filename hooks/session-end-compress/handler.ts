import { existsSync } from 'node:fs';
import type { HookHandler } from 'clawdbot/hooks';
import { spawn } from 'node:child_process';
import path from 'node:path';

const DEFAULT_OPENCLAW_HOME = path.join(process.env.HOME || '', '.openclaw');
const SESSION_MONITOR_PATH =
  process.env.RESONANTOS_SESSION_MONITOR_PATH ||
  path.join(DEFAULT_OPENCLAW_HOME, 'workspace', 'memory', 'session_monitor.py');

/**
 * Extract agent ID from session key.
 * Session keys are formatted as: "agent:{agentId}:{qualifier}"
 * e.g., "agent:strategist:main" -> "strategist"
 */
function extractAgentId(sessionKey: string): string | null {
  const parts = sessionKey.split(':');
  if (parts.length >= 2 && parts[0] === 'agent') {
    return parts[1];
  }
  return null;
}

/**
 * Run the session monitor's compress_final_state for an agent.
 * This is fire-and-forget to avoid blocking the /new command.
 */
function compressFinalState(agentId: string): Promise<void> {
  return new Promise((resolve) => {
    if (!SESSION_MONITOR_PATH || !existsSync(SESSION_MONITOR_PATH)) {
      console.log('[session-end-compress] Session monitor script not configured; skipping.');
      resolve();
      return;
    }

    console.log(`[session-end-compress] Compressing final state for agent: ${agentId}`);
    
    const proc = spawn('python3', [
      SESSION_MONITOR_PATH,
      '--final-state',
      '--agent', agentId
    ], {
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: true,
      env: { ...process.env }
    });
    
    let stdout = '';
    let stderr = '';
    
    proc.stdout?.on('data', (data) => {
      stdout += data.toString();
    });
    
    proc.stderr?.on('data', (data) => {
      stderr += data.toString();
    });
    
    proc.on('close', (code) => {
      if (code === 0) {
        console.log(`[session-end-compress] Completed for ${agentId}`);
        if (stdout.trim()) {
          console.log(`[session-end-compress] ${stdout.trim()}`);
        }
      } else {
        console.error(`[session-end-compress] Failed for ${agentId} (exit ${code})`);
        if (stderr.trim()) {
          console.error(`[session-end-compress] ${stderr.trim()}`);
        }
      }
      resolve();
    });
    
    proc.on('error', (err) => {
      console.error(`[session-end-compress] Spawn error: ${err.message}`);
      resolve();
    });
    
    // Unref to allow parent to exit independently
    proc.unref();
  });
}

const sessionEndCompressHook: HookHandler = async (event) => {
  // Only handle command:new and command:reset events
  if (event.type !== 'command') {
    return;
  }
  
  if (event.action !== 'new' && event.action !== 'reset') {
    return;
  }
  
  // Extract agent ID from session key
  const agentId = extractAgentId(event.sessionKey);
  if (!agentId) {
    console.log(`[session-end-compress] Could not extract agent ID from: ${event.sessionKey}`);
    return;
  }
  
  // Skip compression for certain agents (router, memory itself)
  const skipAgents = ['router', 'memory', 'researcher'];
  if (skipAgents.includes(agentId)) {
    console.log(`[session-end-compress] Skipping agent: ${agentId}`);
    return;
  }
  
  console.log(`[session-end-compress] Triggered for ${agentId} via /${event.action}`);
  
  try {
    // Run compression - this happens BEFORE the session is cleared
    // because command hooks fire before command execution
    await compressFinalState(agentId);
  } catch (err) {
    console.error(`[session-end-compress] Error:`, err instanceof Error ? err.message : String(err));
    // Don't throw - let the /new command continue
  }
};

export default sessionEndCompressHook;
