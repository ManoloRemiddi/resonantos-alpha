# ResonantOS Dashboard

A self-hosted, decentralized AI chatbot management platform.

## Features

### Chatbot Manager
- Create and customize AI chatbots
- Knowledge base upload (PDF, TXT, MD) with RAG search
- Live preview with real-time customization
- Widget embed code generation
- Conversation history and transcripts

### AI Configuration
- Use system API keys or add custom keys
- Model selector: Claude, GPT-4, Gemini
- Per-chatbot configuration

### Payments
- **Stripe:** Card payments for subscriptions
- **Crypto:** SOL, USDT, USDC (Solana), BTC, ETH, USDT, USDC (Ethereum)
- Subscription tiers: Essential ($10), Professional ($50), Business ($150)
- Add-ons: Remove watermark, Extra chatbot, Custom icon, Analytics

### Code Protection
The entire dashboard is obfuscated for IP protection:
- Frontend JS bundled and obfuscated
- Widget code obfuscated per chatbot
- Users self-host but cannot read/clone the source

## Quick Start

```bash
# Development mode
cd dashboard
python server_v2.py

# Production mode
python server_v2.py --port 19100
```

Server runs at: http://localhost:19100

> **Note:** `server.py` is **LEGACY/DEPRECATED**. Use `server_v2.py` for all new development.

## Build Commands

```bash
# Build everything for production
./build.sh

# Build in dev mode (no obfuscation)
./build.sh --dev

# Build specific widget
node scripts/build-widget.js --chatbot-id xxx --tier pro
```

## Android App

APK available at: `~/clawd/projects/resonantos-v3/android/app-debug.apk`

Install on Android device to access dashboard from mobile.

## Directory Structure

```
dashboard/
├── server_v2.py        # Flask backend (ACTIVE - OpenClaw native)
├── server.py           # DEPRECATED - Legacy server (kept for reference)
├── templates/          # HTML templates
├── static/             # JS, CSS, assets
├── build.sh            # Production build script
├── scripts/            # Build tools
├── test-site/          # Widget test site
├── tests/              # E2E tests
├── uploads/            # Knowledge base files
└── chatbots.db         # SQLite database
```

## Tests

```bash
# Run E2E tests
./tests/chatbot-e2e.sh

# Run payment tests
./venv/bin/python -m pytest tests/test_payment_ai.py
```

## Environment Variables

For Stripe payments:
```bash
export STRIPE_SECRET_KEY=sk_live_xxxx
export STRIPE_PUBLISHABLE_KEY=pk_live_xxxx
export STRIPE_WEBHOOK_SECRET=whsec_xxxx
```

## License

Proprietary - ResonantOS
