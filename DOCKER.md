# ResonantOS Dashboard — Docker Setup

Docker is **optional**. Native installation always works — Docker just simplifies dependencies.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS/Windows)
- Linux: `sudo apt install docker.io docker-compose` or use Docker Engine

Verify Docker is working:
```bash
docker run hello-world
docker compose version
```

## Quick Start

```bash
# 1. Start the dashboard (background)
docker compose up -d

# 2. View logs
docker compose logs -f

# 3. Open your browser
open http://localhost:19100
```

That's it — no Python, no venv, no dependency installation needed.

## First-Time Setup

The container reads your existing `~/.openclaw/` config and `dashboard/config.json`.

Before starting, ensure:
- OpenClaw is installed: `npm install -g openclaw`
- Gateway is configured in `~/.openclaw/openclaw.json`

## How It Works

- The container runs the Flask dashboard on port **19100**
- It accesses your host's `~/.openclaw/` config directory (read-only mount)
- It connects to the OpenClaw gateway running **natively** on your machine at `localhost:18789`
- Your browser connects to `localhost:19100` (the container)

## Port Configuration

Default: `19100:19100` (host:container)

To change the host port, edit `docker-compose.yml`:

```yaml
ports:
  - "3000:19100"   # Dashboard now at http://localhost:3000
```

## Updating

```bash
# Rebuild and restart (detached)
docker compose up --build -d
```

## Stopping

```bash
docker compose down
```

To also remove the built image:
```bash
docker compose down --rmi local
```

## Troubleshooting

### "Docker daemon is not running"

**macOS/Windows:** Open Docker Desktop app and wait for it to fully start.

**Linux:**
```bash
sudo systemctl start docker
# or
sudo service docker start
```

### "Port 19100 is already in use"

Something else is using port 19100. Change the port in `docker-compose.yml`:

```yaml
ports:
  - "3000:19100"   # Use port 3000 on the host instead
```

### "Cannot connect to OpenClaw gateway"

The container needs the gateway running **on your host machine** (not inside Docker).

```bash
# Start the gateway natively:
openclaw gateway start
```

The container connects to `localhost:18789` on your host via `host.docker.internal`.

### "Permission denied" on ~/.openclaw

```bash
chmod 700 ~/.openclaw
chmod 600 ~/.openclaw/openclaw.json
```

### "Volume mount denied" on macOS

Grant Docker Desktop access to your home directory:
Docker Desktop → Settings → Resources → File Sharing → add your home folder.

### Container exits immediately

Check logs:
```bash
docker compose logs
```

Common causes:
- Port 19100 already in use → change port mapping
- Missing `dashboard/config.json` → create it: `cp dashboard/config.example.json dashboard/config.json`

## Uninstall

```bash
docker compose down
```

Remove the image if you want a clean slate:
```bash
docker rmi resonantos-dashboard
```

Your `~/.openclaw/` config and `dashboard/config.json` are untouched — they're on your host, not in Docker.

## Docker vs Native

| | Docker | Native |
|---|---|---|
| Python needed | No | Yes |
| Dependencies | Auto | Manual |
| Setup time | ~2 min | ~10 min |
| Gateway access | Via host | Direct |
| Recommended for | Non-devs, quick start | Developers |
