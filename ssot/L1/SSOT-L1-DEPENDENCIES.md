# SSOT-L1: ResonantOS Dependencies
> Updated: 2026-03-26 | Source: Live system audit

## Overview

ResonantOS is a modular system that layers on top of OpenClaw. Not all components are required — the core is OpenClaw + workspace files. Everything else is optional and adds capabilities.

## Tiers

### Tier 0: Required (System Won't Start Without These)
| Dependency | Version | macOS Install | Linux Install | Windows Install | Purpose |
|-----------|---------|--------------|--------------|----------------|---------|
| Node.js | ≥22.x | `brew install node` | `nvm install 22` / package manager | `nvm-windows` or official installer | OpenClaw runtime |
| npm | ≥10.x | comes with Node | comes with Node | comes with Node | Package management |
| OpenClaw | latest | `npm install -g openclaw` | same | same | Core platform |
| Git | ≥2.40 | `brew install git` or Xcode CLT | `apt install git` / `dnf install git` | Git for Windows | Version control, update checking |

### Tier 1: Core ResonantOS (Needed for Full Functionality)
| Dependency | Version | macOS Install | Linux Install | Windows | Purpose |
|-----------|---------|--------------|--------------|---------|---------|
| Python | ≥3.12 | `brew install python` | `apt install python3` | python.org installer | Dashboard, Shield, scripts |
| Flask | ≥3.0 | `pip install flask` | same | same | Dashboard web server |
| flask-cors | ≥6.0 | `pip install flask-cors` | same | same | Dashboard CORS |
| waitress | ≥3.0 | `pip install waitress` | same | same | Production WSGI server |
| requests | ≥2.31 | `pip install requests` | same | same | HTTP client (dashboard API proxying) |
| Ollama | latest | `brew install ollama` | `curl -fsSL https://ollama.ai/install.sh \| sh` | ollama.com installer | Local embeddings (RAG) |
| nomic-embed-text | latest | `ollama pull nomic-embed-text` | same | same | Embedding model for vector search |

### Tier 2: Extensions & Plugins (Recommended)
| Dependency | Install | Purpose |
|-----------|---------|---------|
| LCM (lossless-claw) | `openclaw plugins install @martian-engineering/lossless-claw` | Lossless context management |
| R-Awareness | ships with ResonantOS (`extensions/r-awareness.js`) | SSoT context injection |
| Shield Gate | ships with ResonantOS (`extensions/shield-gate/`) | Security enforcement |
| Coherence Gate | ships with ResonantOS (`extensions/coherence-gate/`) | Task coherence |
| Heuristic Auditor | ships with ResonantOS (`extensions/heuristic-auditor/`) | Behavioral drift detection |
| Usage Tracker | ships with ResonantOS (`extensions/usage-tracker/`) | Token/cost tracking |

### Tier 3: Components (Optional, Add Capabilities)
| Dependency | Version | macOS Install | Linux Install | Purpose |
|-----------|---------|--------------|--------------|---------|
| mangle-server | built from Go source | `go build` in `logician/mangle-service/` | same | Logician reasoning engine |
| Go | ≥1.21 | `brew install go` | `apt install golang` | Required to build mangle-server |
| logician-proxy | Node.js | `npm install` in `logician-proxy/` | same | HTTP-to-gRPC proxy for Logician |
| @grpc/grpc-js | ≥1.x | via logician-proxy package.json | same | gRPC client for Logician |
| Codex CLI | ≥0.114 | `npm install -g @openai/codex` | same | AI coding agent |
| Solana Python SDK | ≥0.36 | `pip install solana solders` | same | Blockchain/wallet features |
| watchdog (Python) | ≥4.0 | `pip install watchdog` | same | Shield file monitoring |

### Tier 4: Development Tools (For Contributing)
| Dependency | Install | Purpose |
|-----------|---------|---------|
| ruff | `pip install ruff` | Python linter + formatter |
| pyright | `pip install pyright` | Type checking |
| pytest | `pip install pytest` | Test runner |
| pytest-cov | `pip install pytest-cov` | Coverage |
| pre-commit | `pip install pre-commit` | Git hook framework |

## System Services (LaunchAgents / systemd)

These run as background services. On macOS, use LaunchAgents. On Linux, use systemd units.

| Service | Binary | Port/Socket | Required? |
|---------|--------|-------------|-----------|
| OpenClaw Gateway | `openclaw gateway` | TCP 18789 | Yes |
| Dashboard | `python3 server_v2.py` | TCP 19100 | Recommended |
| Shield Daemon | `python3 shield/daemon.py` | TCP 9999 | Optional |
| Logician (mangle-server) | `mangle-server -mode unix` | Unix `/tmp/mangle.sock` | Optional |
| Logician Proxy | `node proxy.js` | TCP 8081 | Optional (needed if Logician used) |
| Memory Doorman | `python3 scripts/memory-doorman.py` | — | Optional |
| Watchdog | runs from remote node via SSH | — | Optional |

## Python Package Summary (pip install)

```
# Core (Tier 1)
flask>=3.0
flask-cors>=6.0
waitress>=3.0
requests>=2.31

# Shield (Tier 3)
watchdog>=4.0

# Blockchain (Tier 3)
solana>=0.36
solders>=0.27

# Development (Tier 4)
ruff
pyright
pytest
pytest-cov
pre-commit
```

## Platform Notes

### macOS
- Homebrew is the recommended package manager
- Xcode Command Line Tools required (`xcode-select --install`)
- LaunchAgents go in `~/Library/LaunchAgents/`
- Python 3.14 from Homebrew works; system Python is too old

### Linux
- systemd units replace LaunchAgents
- Templates in `services/systemd/` (to be created)
- Docker alternative: run dashboard + shield in containers

### Windows
- Native Node.js works for OpenClaw
- Python from python.org (not Microsoft Store)
- Services via Task Scheduler or NSSM
- WSL2 recommended for full stack (Logician, Shield daemon)
- Ollama has native Windows support

## Verification Script

```bash
#!/bin/bash
echo "=== ResonantOS Dependency Check ==="
check() { command -v "$1" >/dev/null 2>&1 && echo "✅ $1: $($1 --version 2>&1 | head -1)" || echo "❌ $1: NOT FOUND"; }
check node
check npm
check git
check python3
check pip3
check ollama
check go
check codex
openclaw --version 2>/dev/null && echo "✅ openclaw: $(openclaw --version)" || echo "❌ openclaw: NOT FOUND"
ollama list 2>/dev/null | grep -q nomic-embed-text && echo "✅ nomic-embed-text: installed" || echo "⚠️  nomic-embed-text: not pulled"
python3 -c "import flask" 2>/dev/null && echo "✅ flask: installed" || echo "❌ flask: not installed"
python3 -c "from waitress import serve" 2>/dev/null && echo "✅ waitress: installed" || echo "❌ waitress: not installed"
```
