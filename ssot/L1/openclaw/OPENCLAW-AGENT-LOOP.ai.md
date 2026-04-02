[AI-OPTIMIZED] ~950 tokens | src: openclaw/docs/concepts/agent-loop.md
Updated: 2026-02-14

# Agent Loop (OpenClaw)

Agentic loop: intake → context assembly → model inference → tool execution → streaming replies → persistence. Single serialized run per session with lifecycle/stream events.

## Entry Points
- Gateway RPC: `agent`, `agent.wait`
- CLI: `agent` command

## Flow
1. **`agent` RPC**: validates params, resolves session (sessionKey/sessionId), persists metadata, returns `{ runId, acceptedAt }` immediately
2. **`agentCommand`**: resolves model + thinking/verbose defaults, loads skills snapshot, calls `runEmbeddedPiAgent`, emits lifecycle end/error if embedded loop doesn't
3. **`runEmbeddedPiAgent`**: 
   - serializes via per-session + global queues
   - resolves model + auth, builds pi session
   - subscribes pi events, streams assistant/tool deltas
   - enforces timeout → aborts if exceeded
   - returns payloads + usage metadata
4. **`subscribeEmbeddedPiSession`**: bridges pi events to `agent` stream:
   - tool events → `stream: "tool"`
   - assistant deltas → `stream: "assistant"`
   - lifecycle → `stream: "lifecycle"` (`phase: "start"|"end"|"error"`)
5. **`agent.wait`** via `waitForAgentJob`:
   - waits for lifecycle end/error on `runId`
   - returns `{ status: ok|error|timeout, startedAt, endedAt, error? }`

## Queueing + Concurrency
- Per-session key (lane) + optional global lane serialization
- Prevents tool/session races, keeps history consistent
- Messaging channels choose queue modes (collect/steer/followup)
- See: [Command Queue](/concepts/queue)

## Session + Workspace
- Workspace resolved/created; sandboxed runs use sandbox root
- Skills loaded/reused from snapshot, injected to env + prompt
- Bootstrap/context files resolved, injected to system prompt
- Session write lock acquired, SessionManager prepared before streaming

## Prompt Assembly
- System prompt: OpenClaw base + skills + bootstrap + per-run overrides
- Model-specific limits + compaction reserve enforced
- See: [System prompt](/concepts/system-prompt)

## Hook Systems

### Internal (Gateway)
- **`agent:bootstrap`**: runs building bootstrap files before system prompt finalized
- **Command hooks**: `/new`, `/reset`, `/stop`, etc.
- See: [Hooks](/hooks)

### Plugin
- **`before_agent_start`**: inject context/override system prompt
- **`agent_end`**: inspect final messages + metadata
- **`before_compaction`/`after_compaction`**: observe/annotate compaction
- **`before_tool_call`/`after_tool_call`**: intercept tool params/results
- **`tool_result_persist`**: transform results before transcript write
- **`message_received`/`message_sending`/`message_sent`**: message lifecycle
- **`session_start`/`session_end`**: session boundaries
- **`gateway_start`/`gateway_stop`**: gateway lifecycle
- See: [Plugins](/plugin#plugin-hooks)

## Streaming + Partial Replies
- Assistant deltas streamed from pi-agent-core as `assistant` events
- Block streaming on `text_end` or `message_end`
- Reasoning streamed separately or as block replies
- See: [Streaming](/concepts/streaming)

## Tool Execution + Messaging
- Tool start/update/end emitted on `tool` stream
- Results sanitized for size + image payloads before log/emit
- Messaging tool sends tracked to suppress duplicates

## Reply Shaping + Suppression
- Final payloads: assistant text (+ reasoning) + inline tool summaries (verbose mode) + error text
- `NO_REPLY` filtered from output
- Messaging duplicates removed
- If no renderable payloads + tool error → fallback error reply (unless messaging tool sent user reply)

## Compaction + Retries
- Auto-compaction emits `compaction` events, may trigger retry
- On retry: in-memory buffers + tool summaries reset
- See: [Compaction](/concepts/compaction)

## Event Streams
- `lifecycle`: from `subscribeEmbeddedPiSession` (fallback from `agentCommand`)
- `assistant`: deltas from pi-agent-core
- `tool`: tool events from pi-agent-core

## Chat Channels
- Assistant deltas buffered to chat `delta` messages
- Chat `final` on lifecycle end/error

## Timeouts
- `agent.wait` default: 30s (wait-only), `timeoutMs` param overrides
- Agent runtime: `agents.defaults.timeoutSeconds` = 600s default, enforced in `runEmbeddedPiAgent` abort timer

## Early Termination
- Agent timeout (abort)
- AbortSignal (cancel)
- Gateway disconnect / RPC timeout
- `agent.wait` timeout (wait-only, doesn't stop agent)
