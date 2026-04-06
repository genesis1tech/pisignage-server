# Plan: pisignage-server — Review & Next Steps

## Context

This is a fork of the open-source piSignage server (colloqi/pisignage-server → genesis1tech/pisignage-server) with custom additions for a TSV6 recycling kiosk integration. PR #1 added:
- Python kiosk package (`kiosk/tsv6_pisignage/`) — drop-in replacement for TSV6's VLC player
- Production Docker config (Node 18 Alpine, Mongo 5.0)
- Nginx reverse proxy with WebSocket support
- Hostinger VPS deploy script

The server is deployed on a Hostinger VPS. There are **no tests**, **no SSL**, **hardcoded secrets**, and **default credentials (pi:pi)** in production. These need to be addressed before the system is production-ready.

---

## Progress

| Phase | Status | PR |
|-------|--------|-----|
| Phase 1: Security Hardening | **Done** | [#2](https://github.com/genesis1tech/pisignage-server/pull/2) |
| Phase 2: Operational Readiness | **Done** | [#2](https://github.com/genesis1tech/pisignage-server/pull/2) |
| Phase 3: CI/CD Pipeline | **Done** | [#2](https://github.com/genesis1tech/pisignage-server/pull/2) |
| Phase 4: Python Kiosk Tests | **Done** | TBD |
| Phase 5: Documentation | **Done** | TBD |
| Phase 6: Kiosk Improvements | **Done** | TBD |

---

## Phase 1: Security Hardening (P0) ✅

### 1.1 Environment Variables & Secrets
- Created `.env.example` with all configurable secrets: `SESSION_SECRET`, `MONGOLAB_URI`, `MONGO_INITDB_ROOT_USERNAME/PASSWORD`, `AUTH_USER`, `AUTH_PASSWORD`, `CORS_ALLOWED_ORIGINS`, `DOMAIN`
- Modified `config/env/all.js` — replaced hardcoded `session.secret: 'piSignage'` with `process.env.SESSION_SECRET || require('crypto').randomBytes(32).toString('hex')`
- Added `.env` and `.env.*` to `.gitignore` (with `!.env.example` exception)
- Created `.dockerignore` with `.env*`, `.git`, `.claude`, `__pycache__` to prevent secrets leaking into Docker images

### 1.2 Fix Auth Bypass Bug
- Fixed operator precedence bug in `basicHttpAuth` at `config/express.js` — missing parentheses allowed auth bypass when `authCredentials.user` was falsy
- Added `helmet` middleware for security headers (X-Content-Type-Options, X-Frame-Options, HSTS)
- Added `express-rate-limit` on `/api/` routes (500 req/15min, health endpoint excluded)

### 1.3 Default Credentials Override
- Added env var support (`AUTH_USER`/`AUTH_PASSWORD`) in `basicHttpAuth` middleware to override DB defaults

### 1.4 MongoDB Authentication
- Added `MONGO_INITDB_ROOT_USERNAME`/`MONGO_INITDB_ROOT_PASSWORD` env vars to mongo service in `docker-compose.prod.yml`
- **Note**: `MONGO_INITDB_*` only works on first volume init. For existing deployments, create user via `mongo` shell first
- **Important**: If you set `MONGO_INITDB_ROOT_*`, you MUST also update `MONGOLAB_URI` to include credentials

### 1.5 CORS Restriction
- Replaced origin-reflecting CORS middleware with allowlist from `CORS_ALLOWED_ORIGINS` env var
- Fixed OPTIONS preflight to return 403 for unlisted origins (instead of misleading 200)
- Default: reject cross-origin requests if env var unset

### 1.6 SSL via Certbot (requires DNS pointing to VPS first)
- Updated `scripts/deploy-hostinger.sh` to install certbot
- Added `server_name` comment in `nginx/pisignage.conf` reminding to set domain before certbot
- SSL is a hard prerequisite before Basic Auth is safe over the network

### 1.7 Fix uncaughtException Handler
- `server.js` uncaughtException handler now exits with code 1 so Docker restarts the container (previously swallowed exceptions and continued in corrupt state)

---

## Phase 2: Operational Readiness (P1) ✅

### 2.1 Health Check Endpoint
- Added `GET /api/health` to `config/routes.js` — returns `{ status, mongo, uptime }`
- Bypasses `basicHttpAuth` (early check in middleware)
- Excluded from rate limiter
- Added Docker healthcheck directives to both services in `docker-compose.prod.yml`
- `depends_on: mongo: condition: service_healthy` ensures server waits for healthy Mongo
- Uses `mongo` shell (not `mongosh`) since `mongo:5.0` doesn't include `mongosh`

### 2.2 Graceful Shutdown
- Added `SIGTERM`/`SIGINT` handlers in `server.js` that close HTTP server + mongoose connection
- Force exit after 10s timeout if graceful shutdown hangs

### 2.3 MongoDB Backup Script
- Created `scripts/backup-mongo.sh` — mongodump to `/var/pisignage/backups/`, retains last 7 daily
- Supports MongoDB authentication (reads credentials from `.env`)
- Deploy script sets up daily cron at 2 AM

### 2.4 Cache Settings in Auth Middleware
- Auth middleware now caches settings with 60s TTL instead of hitting MongoDB on every request

---

## Phase 3: CI/CD Pipeline (P2) ✅

### 3.1 GitHub Actions for Fork
- Replaced upstream Docker Hub workflow with fork-specific CI
- Triggers on push to `master` and PRs to `master`
- Jobs: `lint-python` (ruff on kiosk/), `build-docker` (compose build verification)

---

## Phase 4: Testing (P2) ✅

### 4.1 Python Kiosk Tests
- Created `kiosk/tests/` with pytest tests (117 tests total):
  - `test_pisignage_client.py` (29 tests) — discovery, playback actions, player status, asset/playlist listing, error paths, CPU serial reading, caching
  - `test_overlay_manager.py` (49 tests) — state machine transitions, auto-hide timers, cached images, product image display, audio control, preload, cleanup
  - `test_kiosk.py` (35 tests) — initialization, setup, display callbacks, NFC, run lifecycle, cleanup, graceful degradation without TSV6 deps
  - `conftest.py` — mocks tkinter and PIL at import time (pytest_configure hook) so tests run headless
- Added `pytest`, `pytest-cov` to `pyproject.toml` dev dependencies
- Configured `tool.pytest.ini_options`, `tool.coverage.run` (omit `__main__.py`), `tool.coverage.report` (`fail_under = 70`)
- **Coverage: 96%** (418 statements, 17 miss) — exceeds 70% target
- All ruff checks pass

---

## Phase 5: Documentation (P3) ✅

### 5.1 README
- Replaced upstream README with fork-specific content: architecture overview, Docker quick start, dev setup, env var table, production deployment guide (SSL, backups, health check), security notes, kiosk integration link, testing section

### 5.2 Kiosk README
- Created `kiosk/README.md` — how it works (state machine diagram), installation (Pi + dev), event images table (5 required filenames), environment variables, systemd setup, module reference, testing commands, graceful degradation matrix

---

## Phase 6: Kiosk Improvements (P4) ✅

### 6.1 Connection Pooling
- Replaced bare `requests.get/post` calls with `requests.Session` in `PiSignageClient`
- Session stores auth and timeout, reuses TCP connections across requests

### 6.2 Retry for Discovery
- Added `discover_player_async()` method with exponential backoff (default: 5 retries, 5s base delay)
- Replaced old `_discover_pisignage_player` thread in `kiosk.py` with `discover_player_async()`

### 6.3 Watchdog
- Added `WatchdogSec=30` to `tsv6-pisignage-kiosk.service`
- Added `sd_notify("READY=1")` on setup and periodic `sd_notify("WATCHDOG=1")` heartbeat thread
- Graceful no-op when `systemd.daemon` not available (non-Linux dev)

### 6.4 Text Fallback
- Added `FALLBACK_TEXT` mapping for all overlay states (e.g. "Verifying...", "Cannot Accept", etc.)
- Added `_text_label` tkinter Label for text display when images are missing
- `_show_cached_image` falls back to text label when image not in cache, hides text when image is available
- `_do_hide` clears text label on hide

---

## Effort Estimates

| Phase | Items | Effort |
|-------|-------|--------|
| ~~Phase 1~~ | ~~Security hardening (7 items)~~ | ~~5-6 hrs~~ |
| ~~Phase 2~~ | ~~Health check, graceful shutdown, backup, caching~~ | ~~2-3 hrs~~ |
| ~~Phase 3~~ | ~~CI/CD pipeline~~ | ~~2 hrs~~ |
| ~~Phase 4~~ | ~~Python kiosk tests (127 tests, 97% coverage)~~ | ~~3 hrs~~ |
| ~~Phase 5~~ | ~~Documentation~~ | ~~2 hrs~~ |
| ~~Phase 6~~ | ~~Kiosk polish~~ | ~~2 hrs~~ |

## Verification

- Phase 1-3: `docker compose -f docker-compose.prod.yml build`, verify auth, CORS, helmet headers, health endpoint, graceful shutdown, CI passes
- Phase 4-6: `cd kiosk && pytest --cov` passes with 70%+ (currently 97%)
- Phase 5: Read through docs for completeness
