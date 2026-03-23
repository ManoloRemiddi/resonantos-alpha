# ResonantOS Dashboard — Docker Setup

Docker is **optional**. Native installation always works — Docker just simplifies dependencies.

If you do not want Docker, run the installer in native-only mode:

```bash
node install.js --docker=false
```

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
# 1. Set OPENCLAW_HOME (first time only)
# Linux/macOS:
#   export OPENCLAW_HOME="$HOME"
# Windows (PowerShell):
#   setx OPENCLAW_HOME "$env:USERPROFILE"
# Then create .env once:
#   cp .env.example .env

# 2. Start the dashboard (background)
docker compose up -d

# 3. View logs
docker compose logs -f

# 4. Open your browser
open http://localhost:19100
```

That's it — no Python, no venv, no dependency installation needed.

## First-Time Setup

The container reads your existing `~/.openclaw/` config and `dashboard/config.json`.

Before starting, ensure:
- OpenClaw is installed: `npm install -g openclaw`
- Gateway is configured in `~/.openclaw/openclaw.json`

## How It Works

- The container runs the dashboard under a production WSGI server (Waitress) on port **19100**
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

## Performance

- The container runs under Waitress (WSGI). If you see `waitress.queue:Task queue depth is N` in logs during bursts, raise worker threads:
  - Edit `Dockerfile` CMD to use `--threads <N>` (default is 4; Dockerfile uses 8)
  - Rebuild: `docker compose up --build -d`

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

If your `~/.openclaw/openclaw.json` has `wsUrl: "ws://127.0.0.1:18789"`, update it for Docker Desktop:

```json
{
  "gateway": {
    "auth": { "token": "..." },
    "wsUrl": "ws://host.docker.internal:18789"
  }
}
## Linux: Enable Host Networking

On **Linux**, uncomment `network_mode: host` in docker-compose.yml. This makes the container share the host's network namespace, so `127.0.0.1` inside the container IS the host's loopback — the container can reach your native gateway at `localhost:18789` directly:

```yaml
network_mode: host  # Linux only — recommended
```

If you leave it commented (or on macOS/Windows), the container uses `host.docker.internal:18789` via the extra_hosts setting. This works on Docker Desktop but not reliably on Linux.

### "Cannot connect to OpenClaw gateway"

The container needs the gateway running **on your host machine** (not inside Docker).

```bash
# Start the gateway natively:
openclaw gateway start
```

If your `~/.openclaw/openclaw.json` has `wsUrl: "ws://127.0.0.1:18789"`, update it for Docker Desktop:

```json
{
  "gateway": {
    "auth": { "token": "..." },
    "wsUrl": "ws://host.docker.internal:18789"
  }
}
```

```
For Linux hosts, `network_mode: host` can be enabled (see docker-compose.yml) and `127.0.0.1` works.
```

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
