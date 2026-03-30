# Setup Guide

## Prerequisites

- git
- Node.js 22.12+
- Python 3
- pip

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/ResonantOS/resonantos-alpha.git
cd resonantos-alpha

# 2. Checkout dev branch (if you want latest changes)
git checkout dev

# 3. Run installer
node install.js
```

To skip Docker-related setup and use native-only mode:

```bash
node install.js --docker=false
```

The installer will:
- Install OpenClaw globally (if not present)
- Copy extensions to ~/.openclaw/extensions/
- Set up workspace templates
- Install dashboard dependencies (creates venv)
- Create config from example

## Dashboard

```bash
cd dashboard
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
python server_v2.py
# Open http://localhost:19100
```

## Starting OpenClaw

```bash
openclaw gateway start
```

## Configuration

Edit `dashboard/config.json` with your Solana addresses.

## Architecture

See `docs/SUPPORTED-MATRIX.md` for feature classifications.

## Troubleshooting

### Dashboard won't start
- Check `dashboard/venv/` exists
- Try: `pip install flask flask-cors psutil websocket-client solana solders`

### Extensions not loading
- Check `~/.openclaw/extensions/` has the .js files
- Check `~/.openclaw/openclaw.json` has extensions registered

### Path issues
- This repo uses `resonantos-alpha` as the directory name
- Old references to `resonantos-augmentor` are deprecated
