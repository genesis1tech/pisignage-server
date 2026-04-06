#!/bin/bash
set -euo pipefail

# piSignage Server Deployment Script for Hostinger VPS
# Usage: ssh into VPS, clone repo, run this script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== piSignage Server Deployment ==="
echo "Project dir: $PROJECT_DIR"

# 1. Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "Docker installed. You may need to log out and back in for group changes."
fi

# 2. Install Docker Compose plugin if not present
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose plugin..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# 3. Install nginx and certbot if not present
if ! command -v nginx &> /dev/null; then
    echo "Installing nginx..."
    sudo apt-get update
    sudo apt-get install -y nginx
fi

if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    sudo apt-get update
    sudo apt-get install -y certbot python3-certbot-nginx
fi

# 4. Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "WARNING: No .env file found!"
    echo "Copy .env.example to .env and fill in values before deploying:"
    echo "  cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env"
    echo ""
    exit 1
fi

# 5. Create required directories
echo "Creating media directories..."
sudo mkdir -p /var/pisignage/media/_thumbnails
sudo mkdir -p /var/pisignage/data

# 6. Copy nginx config
echo "Configuring nginx..."
sudo cp "$PROJECT_DIR/nginx/pisignage.conf" /etc/nginx/sites-available/pisignage
sudo ln -sf /etc/nginx/sites-available/pisignage /etc/nginx/sites-enabled/pisignage
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 7. Build and start containers
echo "Building and starting piSignage server..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.prod.yml up -d --build

# Set up daily MongoDB backup cron
echo "Setting up daily MongoDB backup..."
sudo cp "$PROJECT_DIR/scripts/backup-mongo.sh" /usr/local/bin/pisignage-backup
sudo chmod +x /usr/local/bin/pisignage-backup
(crontab -l 2>/dev/null | grep -v pisignage-backup; echo "0 2 * * * /usr/local/bin/pisignage-backup $PROJECT_DIR") | crontab -

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "piSignage server is running at http://$(hostname -I | awk '{print $1}'):3000"
echo "nginx proxy at http://$(hostname -I | awk '{print $1}')"
echo "Health check: curl http://localhost:3000/api/health"
echo ""
echo "IMPORTANT: Set AUTH_USER and AUTH_PASSWORD in .env to override default pi:pi credentials"
echo ""
echo "Next steps:"
echo "  1. Point your domain DNS to this server's IP"
echo "  2. Update server_name in /etc/nginx/sites-available/pisignage"
echo "  3. Install SSL: sudo certbot --nginx -d your-domain.com"
echo "  4. Update piSignage player to point at https://your-domain.com"
