# AGENTS.md — ResonantOS Alpha (Public Repo)

## What This Is

ResonantOS is an experience layer built on [OpenClaw](https://github.com/openclaw/openclaw). This is the **public alpha repo** — everything here is user-facing and must work for external testers.

## Architecture

```
resonantos-alpha/
├── dashboard/           # Flask web UI (server_v2.py) on port 19100
│   ├── server_v2.py     # Main server — all routes
│   ├── templates/       # Jinja2 HTML templates
│   ├── static/          # CSS, JS, images
│   └── config.json      # Runtime config (network, program IDs)
├── extensions/          # OpenClaw plugin extensions
│   ├── r-memory.js      # Conversation compression (before_turn / after_turn hooks)
│   └── r-awareness.js   # Contextual document injection
├── shield/              # Security components
│   ├── file_guard.py    # File protection
│   └── data_leak_scanner.py  # Pre-push secret scanning
├── solana-toolkit/      # Solana blockchain utilities (NFTs, tokens, wallets)
├── ssot-template/       # Single Source of Truth doc templates
├── tools/               # Maintenance scripts
└── install.js           # One-command installer
```

## Key Components

### Dashboard (server_v2.py)
- Flask app, port 19100
- Pages: home, agents, chatbots, r-memory, wallet, bounties, tribes, projects, docs, settings
- Imports from `solana-toolkit/` for blockchain operations
- Uses `config.json` for network settings and program IDs
- Templates use Jinja2 with `base.html` as layout

### Solana Toolkit
- `wallet.py` — SolanaWallet class, reads keypair from `~/.config/solana/id.json`
- `nft_minter.py` — NFTMinter for soulbound NFTs (identity, license, manifesto)
- `token_manager.py` — TokenManager for $RCT and $RES token operations
- `symbiotic_client.py` — Symbiotic Wallet PDA operations
- `protocol_nft_minter.py` — Protocol Store NFT minting
- Network: DevNet by default

### Extensions
- Must export a function that receives an `api` object
- Hooks: `before_turn`, `after_turn`, `before_tool_call`, `after_tool_call`
- Extensions live in `~/.openclaw/extensions/` when installed

## Conventions

- **Python**: Flask, no type hints required, f-strings preferred
- **JavaScript**: CommonJS (`require`), no TypeScript
- **HTML/CSS**: Vanilla JS in templates, no frameworks
- **Blockchain**: Solana DevNet, Anchor framework for on-chain programs
- **Error handling**: Graceful fallbacks. If solana-toolkit is unavailable, routes should return friendly errors, not crash

## Testing

- Dashboard: `cd dashboard && python3 server_v2.py` then hit `http://localhost:19100`
- Solana operations need: `pip3 install solana solders anchorpy`
- Phantom wallet browser extension needed for wallet features (enable Developer Mode + Devnet)

## Important Rules

1. **No private data.** This is a public repo. No keys, no personal paths, no memory files.
2. **Graceful degradation.** If a dependency is missing, show a helpful error, don't crash.
3. **DevNet only.** All Solana operations target devnet. Never mainnet.
4. **Test before claiming fixed.** Run the server, hit the route, verify the response.
