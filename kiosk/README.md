# TSV6 piSignage Kiosk

Python package that integrates piSignage digital signage with TSV6 recycling kiosk hardware on Raspberry Pi. Replaces TSV6's VLC-based video player with piSignage while adding a tkinter overlay for barcode flow events.

## How It Works

1. **piSignage handles all video playback** — runs in Chromium, managed by piSignage server
2. **Tkinter overlay sits on top** — hidden during normal playback, raised instantly on barcode scan
3. **State machine drives the overlay** — transitions between event images during the recycling flow:

```
IDLE → PROCESSING → DEPOSIT_WAITING → PRODUCT_DISPLAY → IDLE
IDLE → PROCESSING → NO_MATCH → IDLE
IDLE → PROCESSING → RECYCLE_FAILURE → IDLE
IDLE → PROCESSING → QR_NOT_ALLOWED → IDLE
```

4. **piSignage API client** — optionally pauses/resumes video during barcode flow

## Installation

### On Raspberry Pi

```bash
cd ~/pisignage-server/kiosk
pip3 install .

# With Pi hardware support (AWS IoT, serial, NFC):
pip3 install ".[pi]"
```

### Development (off-Pi)

```bash
cd kiosk
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

### Event Images

Create an `event_images/` directory alongside the kiosk with these required images:

| Filename | State | Shown When |
|---|---|---|
| `image_verify.jpg` | PROCESSING | Barcode scanned, verifying with AWS |
| `cannot_accept.jpg` | NO_MATCH | Barcode not recognized |
| `barcode_not_qr.jpg` | QR_NOT_ALLOWED | QR code scanned instead of barcode |
| `deposit_waiting.jpg` | DEPOSIT_WAITING | Waiting for item deposit |
| `item_not_detected.jpg` | RECYCLE_FAILURE | ToF sensor did not detect item |

Images are resized to screen resolution at startup. Recommended: 800x480 JPG.

### Environment Variables

| Variable | Purpose |
|---|---|
| `PISIGNAGE_SERVER_URL` | piSignage server URL (e.g. `https://signage.example.com`) |
| `PISIGNAGE_USER` | HTTP Basic Auth username |
| `PISIGNAGE_PASSWORD` | HTTP Basic Auth password |
| `EVENT_IMAGES_DIR` | Path to event images directory (default: `event_images`) |

### systemd Service

Install the service file for auto-start:

```bash
sudo cp tsv6-pisignage-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tsv6-pisignage-kiosk
```

Edit the service file to set:
- `PISIGNAGE_SERVER_URL`, `PISIGNAGE_USER`, `PISIGNAGE_PASSWORD`
- `WorkingDirectory` to your kiosk install path

## Running

```bash
# Standalone (no TSV6 hardware):
python3 -m tsv6_pisignage

# Via production_main.py (full TSV6 integration):
# Imported as drop-in replacement for EnhancedVideoPlayer
```

## Testing

```bash
pytest --cov                    # 117 tests, 96% coverage
ruff check tsv6_pisignage/ tests/   # lint
```

## Module Reference

| Module | Purpose |
|---|---|
| `pisignage_client.py` | REST client for piSignage server (discovery, playback, playlists) |
| `overlay_manager.py` | Tkinter fullscreen overlay with state machine |
| `kiosk.py` | Main orchestrator — barcode callbacks, NFC, lifecycle |
| `__main__.py` | Standalone launcher |

## Graceful Degradation

The kiosk works without Pi hardware:
- Missing TSV6 packages (AWS IoT, serial, NFC) → features disabled, overlay still works
- Missing piSignage server → overlay works standalone, no remote control
- Missing event images → overlay shows nothing (add text fallback in future)
- Missing `amixer` → audio mute/unmute skipped (dev machines)
- Missing `PIL`/`Pillow` → overlay disabled, kiosk still runs
