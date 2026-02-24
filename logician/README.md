# Logician — Deterministic Policy Engine for AI Agents

> **Part of ResonantOS** — an experience layer on [OpenClaw](https://github.com/openclaw/openclaw)

The Logician is a Mangle/Datalog engine that provides **provable, deterministic policy enforcement** for AI agent systems. Instead of hoping agents follow instructions, Logician *proves* they can or can't do something — before it happens.

## Why Deterministic Policy?

AI agents are powerful but unreliable at following rules. They hallucinate, drift, and override instructions. The Logician solves this by moving policy enforcement **outside the AI's reasoning loop**:

| Approach | Reliability | Cost | Speed |
|----------|-------------|------|-------|
| Prompt instructions | ~60% | Tokens per check | Slow |
| **Logician rules** | **100%** | **Zero tokens** | **<1ms** |

A Logician rule is a mathematical proof, not a suggestion. If a rule says an agent can't spawn a subprocess, it *cannot* — regardless of what the prompt says.

## Architecture

```
Agent (OpenClaw) → Shield Gate (extension) → Logician (gRPC) → Mangle Engine
                                                                     ↑
                                                              production_rules.mg
```

1. **Mangle Engine** — Google's Datalog implementation. Evaluates rules as mathematical proofs.
2. **gRPC Service** — Wraps the engine in a server accessible via Unix socket or TCP.
3. **Shield Gate** — OpenClaw extension that intercepts tool calls and checks them against Logician rules.
4. **Rule Files** — `.mg` files containing your policies in Mangle syntax.

## Quick Start

### Prerequisites

- Go 1.22+ (`brew install go` or [golang.org](https://golang.org/dl/))
- OpenClaw installed and running

### Install

```bash
cd logician
./scripts/install.sh
```

This will:
1. Build the Mangle gRPC server from source
2. Install a LaunchAgent (macOS) or systemd service (Linux) 
3. Load the example rules
4. Verify the service is running

### Manual Build

```bash
cd mangle-service
go get ./...
go build -o mangle-server ./server/main.go
```

### Start the Service

```bash
# Using the control script
./scripts/logician_ctl.sh start

# Or manually
./mangle-service/mangle-server --source=rules/example-rules.mg --mode=unix --sock-addr=/tmp/mangle.sock
```

### Test It

```bash
# Query all registered agents
./scripts/logician_ctl.sh query 'agent(X)'

# Check if the orchestrator can spawn a coder
./scripts/logician_ctl.sh query 'spawn_allowed(/orchestrator, /coder)'

# Run the Python demo
python3 client/logician_client.py
```

## Writing Rules

Rules use Mangle syntax — an extension of Datalog. If you know SQL, you can learn Mangle in 10 minutes.

### Facts (Simple Data)

```mangle
# Register agents
agent(/orchestrator).
agent(/coder).
agent(/researcher).

# Set trust levels (1-5)
trust_level(/orchestrator, 5).
trust_level(/coder, 3).
trust_level(/researcher, 3).
```

### Permissions

```mangle
# Who can spawn whom
can_spawn(/orchestrator, /coder).
can_spawn(/orchestrator, /researcher).
can_spawn(/coder, /tester).

# Explicit blocks
blocked_spawn(/coder, /orchestrator).
```

### Derived Rules (Logic)

```mangle
# Spawn is allowed if permitted AND not blocked
spawn_allowed(From, To) :- can_spawn(From, To), !blocked_spawn(From, To).

# Agent can use dangerous tools only if trust >= 3
can_use_dangerous(Agent, Tool) :-
  can_use_tool(Agent, Tool),
  dangerous_tool(Tool),
  trust_level(Agent, Level),
  Level >= 3.
```

### Security Patterns

```mangle
# Injection detection (string matching)
injection_pattern("ignore previous instructions").
injection_pattern("jailbreak").
injection_pattern("pretend you are").

# Destructive command blocking
destructive_pattern("rm -rf").
destructive_pattern("drop database").

# Protected paths
protected_path("/etc/").
protected_path("~/.ssh/").
```

See `rules/templates/` for more patterns you can customize.

## Rule Quality Protocol

Not all rules are created equal. A rule that "feels right" but can't be mechanically evaluated is a wish, not a rule.

Every rule should pass **Three Gates** before entering production:

### Gate 0: Intent Recovery
Before writing a rule, ask: "What am I trying to protect against?" The intent is the invariant — the implementation is replaceable.

### Gate 1: Measurable
Can a machine evaluate this without AI reasoning? If it requires "understanding," it's not a Logician rule — put it in your agent's system prompt.

### Gate 2: Binary
Does it produce exactly YES or NO? No "maybe," no "it depends."

### Gate 3: Falsifiable
Can you write a test that SHOULD fail? If every input passes, the rule enforces nothing.

Use the **Rule Writer Skill** (`skills/rule-writer/SKILL.md`) to guide your rule creation process.

## Integration with OpenClaw

The Logician integrates with OpenClaw through the Shield Gate extension. See `extensions/shield-gate/` in the ResonantOS repo for the reference implementation.

Basic integration pattern:

```javascript
// In your OpenClaw extension
const { execSync } = require("child_process");

function logicianProves(query) {
  try {
    const result = execSync(
      `grpcurl -plaintext -proto proto/mangle.proto ` +
      `-d '{"query": "${query}"}' ` +
      `unix:///tmp/mangle.sock mangle.Mangle.Query`,
      { timeout: 2000 }
    );
    return result.toString().includes("answer");
  } catch {
    return false; // Fail-open or fail-closed — your choice
  }
}

// Usage in before_tool_call hook
api.on("before_tool_call", (event, ctx) => {
  if (event.toolName === "exec") {
    const allowed = logicianProves(`can_use_tool(/${ctx.agentId}, /exec)`);
    if (!allowed) return { block: true, blockReason: "Not authorized for exec" };
  }
  return {};
});
```

## File Structure

```
logician/
├── README.md              ← You are here
├── mangle-service/        ← Go gRPC server (Google Mangle engine)
│   ├── server/main.go
│   ├── service/service.go
│   ├── client/main.go
│   ├── proto/mangle.proto
│   └── example/demo.mg
├── rules/                 ← Your policy rules
│   ├── example-rules.mg   ← Starter rule set
│   └── templates/         ← Rule patterns to customize
├── scripts/               ← Management scripts
│   ├── install.sh
│   └── logician_ctl.sh
├── client/                ← Python client library
│   └── logician_client.py
└── skills/                ← OpenClaw skills
    └── rule-writer/       ← AI-assisted rule creation
        └── SKILL.md
```

## Credits

- **Mangle Engine** by Google — [github.com/google/mangle](https://github.com/google/mangle)
- **gRPC Service** by Burak Emir — [github.com/burakemir/mangle-service](https://github.com/burakemir/mangle-service)
- **ResonantOS Integration** — Policy framework, Shield Gate, Rule Quality Protocol

## License

Apache 2.0 — Same as the Mangle engine.
