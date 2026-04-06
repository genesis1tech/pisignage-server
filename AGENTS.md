# AGENTS.md

## Project Overview

piSignage server — Node.js/Express app that manages piSignage digital signage players over LAN/private networks. MongoDB backend, Pug templates, Socket.IO real-time communication. Includes a Python kiosk package (`kiosk/tsv6_pisignage/`) for TSV6 recycling kiosk hardware integration.

## Tech Stack

- **Runtime:** Node.js (Docker image uses node:18-alpine)
- **Framework:** Express 4.x with Mongoose 5.x (MongoDB 5.0)
- **Views:** Pug
- **Real-time:** Three Socket.IO instances (legacy `919.socket.io`, modern `socket.io` on `/newsocket.io`, WebSocket-only on `/wssocket.io`) plus a raw `ws` WebSocket server on `/websocket`
- **Frontend:** AngularJS (in `public/`, served as static files)
- **System deps:** ffmpeg, ffprobe, imagemagick (for video conversion and thumbnail generation)
- **Kiosk:** Python 3.11+ (`kiosk/`) with tkinter overlay, uses `ruff` for linting

## Commands

```bash
# Dev server (uses nodemon)
npm start
# Equivalent to: node server.js (NODE_ENV defaults to 'development')

# Docker (production build)
docker compose -f docker-compose.prod.yml up -d --build

# Lint kiosk Python
pip install ruff && ruff check kiosk/

# Health check
curl http://localhost:3000/api/health
```

No test suite exists. CI only lints Python (`ruff check kiosk/`) and builds the Docker image.

## Architecture

```
server.js              # Entry point — starts Express, MongoDB, all Socket.IO/WebSocket servers
config/
  config.js            # Merges env/all.js + env/{NODE_ENV}.js via lodash
  express.js           # Middleware stack (helmet, rate-limit, CORS, Basic Auth, routes)
  routes.js            # API route definitions (/api/files, /api/playlists, /api/groups, etc.)
app/
  models/              # Mongoose schemas (assets, group, label, player, settings)
  controllers/         # Route handlers + socket controllers + scheduler
  others/              # file-util, process-file, restware, system-check
  views/               # Pug templates
public/                # Static AngularJS frontend (served as-is)
kiosk/                 # Python package — TSV6 kiosk integration (separate deploy target)
scripts/               # Deploy (Hostinger VPS), MongoDB backup, OS install scripts
nginx/                 # Reverse proxy config for production
```

## Key Conventions and Gotchas

- **No build step for frontend** — `public/` is served as static files directly
- **Mongoose models auto-loaded** — `server.js` reads all files in `app/models/` at startup via `fs.readdirSync`
- **Config is lodash-merged** — `config/env/all.js` (base) merged with `config/env/{NODE_ENV}.js`; env vars (`MONGOLAB_URI`, `PORT`, `AUTH_USER`, `AUTH_PASSWORD`, `SESSION_SECRET`, `CORS_ALLOWED_ORIGINS`) override hardcoded values
- **Auth is DB-backed with env override** — HTTP Basic Auth credentials come from the `settings` MongoDB document by default (initially `pi:pi`); `AUTH_USER`/`AUTH_PASSWORD` env vars take precedence
- **Health endpoint bypasses auth** — `/api/health` is explicitly skipped in `express.js:basicHttpAuth`
- **Media directory is sibling** — Default media path is `../media` (relative to project root, NOT inside the project). Must exist with `_thumbnails` subdirectory or thumbnails silently fail
- **Session secret** — Falls back to a random hex string if `SESSION_SECRET` env var is unset; this means sessions invalidate on restart unless set
- **Four real-time transports** — Old Socket.IO (`/socket.io`), new Socket.IO (`/newsocket.io`), WebSocket-only Socket.IO (`/wssocket.io`), raw WebSocket (`/websocket`). All must be proxy-upgraded through nginx
- **CORS is allowlist-based** — Only origins in `CORS_ALLOWED_ORIGINS` (comma-separated) get CORS headers; unset means no cross-origin access
- **Production deploy** — Uses `docker-compose.prod.yml` (builds locally), nginx reverse proxy, optional certbot SSL. See `scripts/deploy-hostinger.sh`

## Environment Variables

See `.env.example` for full reference. Critical ones:

| Variable | Default | Purpose |
|---|---|---|
| `NODE_ENV` | `development` | Selects config file under `config/env/` |
| `MONGOLAB_URI` | `mongodb://127.0.0.1:27017/pisignage-server-dev` | MongoDB connection |
| `PORT` | `3000` | Server port |
| `AUTH_USER` / `AUTH_PASSWORD` | (none — uses DB settings, initially `pi:pi`) | Override HTTP Basic Auth |
| `SESSION_SECRET` | (random, changes per restart) | Cookie signing |
| `CORS_ALLOWED_ORIGINS` | (empty — no CORS) | Comma-separated allowed origins |

## Kiosk (Python)

- Located at `kiosk/tsv6_pisignage/` — a Raspberry Pi kiosk app that replaces TSV6's VLC player with piSignage
- Runs as a systemd service (`kiosk/tsv6-pisignage-kiosk.service`) that starts after `pisignage.service`
- Entry point: `python3 -m tsv6_pisignage.kiosk`
- Dependencies split: core (`requests`, `Pillow`) vs Pi hardware (`awscrt`, `awsiotsdk`, `pyserial`, `qrcode` via `[pi]` extras)
- Linted with `ruff` in CI
