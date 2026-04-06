# pisignage-server

Fork of [colloqi/pisignage-server](https://github.com/colloqi/pisignage-server) with TSV6 recycling kiosk integration, Docker production config, security hardening, and operational tooling.

Manages piSignage digital signage players over LAN/private networks. Node.js/Express backend, MongoDB, Pug templates, Socket.IO real-time, AngularJS frontend.

## Architecture

```
server.js              # Entry point — Express, MongoDB, Socket.IO/WebSocket servers
config/
  config.js            # Merges env/all.js + env/{NODE_ENV}.js
  express.js           # Middleware (helmet, rate-limit, CORS, Basic Auth)
  routes.js            # API routes (/api/files, /api/playlists, /api/groups, etc.)
app/
  models/              # Mongoose schemas (assets, group, label, player, settings)
  controllers/         # Route handlers + socket controllers + scheduler
  others/              # file-util, process-file, restware, system-check
  views/               # Pug templates
public/                # AngularJS frontend (static, no build step)
kiosk/                 # Python TSV6 kiosk integration (separate deploy)
scripts/               # Deploy, MongoDB backup, OS install scripts
nginx/                 # Reverse proxy config for production
```

## Quick Start (Docker)

1. Clone and configure:

```bash
git clone https://github.com/genesis1tech/pisignage-server.git
cd pisignage-server
cp .env.example .env
# Edit .env — set SESSION_SECRET, AUTH_USER, AUTH_PASSWORD at minimum
```

2. Deploy:

```bash
# On a fresh VPS:
bash scripts/deploy-hostinger.sh

# Or manually:
docker compose -f docker-compose.prod.yml up -d --build
```

3. Access at `http://your-server:3000` (or via nginx on port 80)

## Quick Start (Development)

```bash
# Prerequisites: Node.js 18+, MongoDB 5.0+, ffmpeg, imagemagick
npm install
mkdir -p ../media/_thumbnails
npm start    # starts on http://localhost:3000
```

Default credentials: `pi:pi` (change in Settings or via `AUTH_USER`/`AUTH_PASSWORD` env vars).

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `NODE_ENV` | `development` | Config file selector |
| `MONGOLAB_URI` | `mongodb://127.0.0.1:27017/pisignage-server-dev` | MongoDB connection |
| `PORT` | `3000` | Server port |
| `SESSION_SECRET` | (random, changes per restart) | Cookie signing — **set this** |
| `AUTH_USER` / `AUTH_PASSWORD` | (none — uses DB, initially `pi:pi`) | HTTP Basic Auth override |
| `CORS_ALLOWED_ORIGINS` | (empty — no CORS) | Comma-separated allowed origins |
| `DOMAIN` | (none) | Domain for SSL/certbot |

See `.env.example` for full reference.

## Production Deployment

Deployed on a Hostinger VPS using Docker + nginx reverse proxy.

### SSL Setup

1. Point DNS to your VPS IP
2. Update `server_name` in `nginx/pisignage.conf`
3. Run: `sudo certbot --nginx -d your-domain.com`
4. Uncomment the HTTPS block in `nginx/pisignage.conf`

### MongoDB Backups

Daily backups at 2 AM (set up by deploy script):

```bash
# Manual backup:
bash scripts/backup-mongo.sh /path/to/project
```

Retains last 7 daily backups in `/var/pisignage/backups/`.

### Health Check

```bash
curl http://localhost:3000/api/health
# Returns: {"status":"ok","mongo":"connected","uptime":12345}
```

## Security Notes

- **Change default credentials** — Set `AUTH_USER`/`AUTH_PASSWORD` in `.env`
- **Set `SESSION_SECRET`** — Otherwise sessions invalidate on every restart
- **Enable SSL** — HTTP Basic Auth sends credentials in plaintext; SSL is mandatory for production
- **CORS** — Only origins in `CORS_ALLOWED_ORIGINS` are allowed cross-origin access
- **Rate limiting** — 500 requests per 15 minutes on `/api/` routes
- **Security headers** — helmet middleware (X-Content-Type-Options, X-Frame-Options, HSTS)
- **MongoDB auth** — Set `MONGO_INITDB_ROOT_USERNAME`/`MONGO_INITDB_ROOT_PASSWORD` for new deployments

## TSV6 Kiosk Integration

See [kiosk/README.md](kiosk/README.md) for the Python kiosk package that integrates piSignage with TSV6 recycling kiosk hardware.

## Testing

```bash
# Python kiosk tests (117 tests, 96% coverage)
cd kiosk
pip install -e ".[dev]"
pytest --cov

# Python lint
ruff check kiosk/ tests/
```

No test suite exists for the Node.js server.

## Features

- Player management — auto-discovery, monitoring
- Group management — display settings, playlist assignment
- Asset management — upload, video conversion (ffmpeg), thumbnails
- Playlist management — drag-to-reorder, layouts, ticker, ad scheduling
- Four real-time transports — Socket.IO (3 variants) + raw WebSocket

## System Requirements

- 2GB RAM minimum
- 30GB+ storage (video assets)
- Linux (Docker) or macOS (development)
