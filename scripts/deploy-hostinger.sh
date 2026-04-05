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

# 3. Install nginx if not present
if ! command -v nginx &> /dev/null; then
    echo "Installing nginx..."
    sudo apt-get update
    sudo apt-get install -y nginx
fi

# 4. Create required directories
echo "Creating media directories..."
sudo mkdir -p /var/pisignage/media/_thumbnails
sudo mkdir -p /var/pisignage/data

# 5. Copy nginx config
echo "Configuring nginx..."
sudo cp "$PROJECT_DIR/nginx/pisignage.conf" /etc/nginx/sites-available/pisignage
sudo ln -sf /etc/nginx/sites-available/pisignage /etc/nginx/sites-enabled/pisignage
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 6. Build and start containers
echo "Building and starting piSignage server..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "piSignage server is running at http://$(hostname -I | awk '{print $1}'):3000"
echo "nginx proxy at http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Default credentials: pi:pi (change in Settings after login)"
echo ""
echo "Next steps:"
echo "  1. Point your domain DNS to this server's IP"
echo "  2. Install SSL: sudo certbot --nginx -d your-domain.com"
echo "  3. Uncomment HTTPS block in /etc/nginx/sites-available/pisignage"
echo "  4. Update piSignage player to point at https://your-domain.com"
