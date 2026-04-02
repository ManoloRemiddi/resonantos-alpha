# ResonantOS

**A Multi-Agent AI Operating System for Human-AI Collaboration**

---

## What is ResonantOS?

ResonantOS is a sovereign AI operating system that orchestrates multiple AI agents working together as a unified system. Unlike single-agent assistants, ResonantOS enables specialized agents (Strategist, Coder, Designer, Researcher) to collaborate on complex tasks while preserving human agency.

**Core Principles:**
- 🛡️ **Sovereignty** — You own your data, your agents, your system
- 🤝 **Collaboration** — AI as partner, not tool
- 🔒 **Security** — Built-in protection against prompt injection and data exfiltration
- 🧠 **Memory** — Persistent context across sessions

---

## Components

```
resonantos/
├── dashboard/      # Control center UI (Python/Flask)
├── shield/         # Symbiotic Shield - security layer
├── logician/       # Prolog-based policy engine
├── android-app/    # Mobile companion app
├── architecture/   # System design docs
└── docs/           # Documentation
```

### Dashboard
Web-based control center for managing agents, viewing activity, and configuring the system.

### Shield
The Symbiotic Shield protects against:
- Prompt injection attacks
- Data exfiltration attempts
- Jailbreak attempts
- Unauthorized agent-to-agent communication

### Logician
Prolog-based policy engine for declarative access control and agent permissions.

---

## Quick Start

```bash
# Clone
git clone <repo-url> resonantos
cd resonantos

# Install Solana CLI (required for token/NFT operations)
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
solana config set --url https://api.devnet.solana.com

# Start Dashboard
cd dashboard
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python server.py

# Start Shield (separate terminal)
cd shield
./shield_ctl.sh start
```

Dashboard: http://localhost:19100

---

## Philosophy

ResonantOS is built on **Augmentatism** — the practice of conscious human-AI collaboration that preserves human sovereignty. We reject both AI doomerism and blind acceleration. Instead, we build systems where humans and AI evolve together.

Read more in the repository philosophy and architecture documents under `ssot/` and `docs/`.

---

## Status

🚧 **Active Development** — This is a working system, not vaporware. Components are functional but evolving rapidly.

---

## Related Projects

- Resonant Economy — DAO and tokenomics layer
- Augmentatism — Philosophy and framework

---

## License

MIT

---

*"The goal is not to build AI that replaces humans, but AI that makes humans more human."*
