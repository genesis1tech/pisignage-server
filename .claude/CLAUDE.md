# Local Development Notes

## Recent Changes

### minor: TSV6-piSignage kiosk integration and production deployment - 2026-04-05
- Branch: `minor/tsv6-pisignage-kiosk-integration`
- PR: https://github.com/genesis1tech/pisignage-server/pull/1
- Summary: Added kiosk Python package (kiosk/tsv6_pisignage/) as drop-in replacement for TSV6's VLC player. piSignage handles video playback; tkinter overlay manages barcode flow. Production Docker config (Node 18, MongoDB 5.0), nginx reverse proxy with WebSocket support, Hostinger VPS deploy script, systemd service with piSignage startup ordering.
