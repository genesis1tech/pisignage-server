#!/bin/bash
set -euo pipefail

# MongoDB Backup Script for piSignage Server
# Usage: backup-mongo.sh [project-dir]
# Retains last 7 daily backups

PROJECT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_DIR="/var/pisignage/backups"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/pisignage-$DATE.gz"
RETENTION_DAYS=7

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting MongoDB backup..."

# Build mongodump command with optional auth
MONGODUMP_CMD="mongodump --archive --gzip --db=pisignage-server-dev"

# Source .env for Mongo credentials if available
if [ -f "$PROJECT_DIR/.env" ]; then
    MONGO_USER=$(grep -E "^MONGO_INITDB_ROOT_USERNAME=" "$PROJECT_DIR/.env" | cut -d= -f2-)
    MONGO_PASS=$(grep -E "^MONGO_INITDB_ROOT_PASSWORD=" "$PROJECT_DIR/.env" | cut -d= -f2-)
    if [ -n "$MONGO_USER" ] && [ -n "$MONGO_PASS" ]; then
        MONGODUMP_CMD="$MONGODUMP_CMD --username=$MONGO_USER --password=$MONGO_PASS --authenticationDatabase=admin"
    fi
fi

# Run mongodump inside the running container
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" exec -T mongo \
    $MONGODUMP_CMD > "$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup complete: $BACKUP_FILE ($BACKUP_SIZE)"

# Remove backups older than retention period
find "$BACKUP_DIR" -name "pisignage-*.gz" -mtime +$RETENTION_DAYS -delete
REMAINING=$(find "$BACKUP_DIR" -name "pisignage-*.gz" | wc -l)
echo "Retained $REMAINING backup(s)"
