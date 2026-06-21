#!/bin/bash
# ── Basira Backup Script ───────────────────────────────────────────────
# Run this daily via cron: 0 2 * * * /opt/basira/backup.sh
# ────────────────────────────────────────────────────────────────────────

set -e

# Configuration
BACKUP_DIR="/opt/basira-backups"
APP_DIR="/opt/basira"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="basira-backup-$DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# Backup Redis
echo "Backing up Redis..."
docker run --rm \
    -v basira_redis_data:/data \
    -v "$BACKUP_DIR/$BACKUP_NAME":/backup \
    alpine tar czf /backup/redis.tar.gz -C /data . 2>/dev/null || echo "Redis backup skipped"

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
docker exec basira-postgres-1 pg_dump -U basira basira > "$BACKUP_DIR/$BACKUP_NAME/postgres.sql" 2>/dev/null || echo "PostgreSQL backup skipped"

# Backup Qdrant
echo "Backing up Qdrant..."
docker run --rm \
    -v basira_qdrant_data:/qdrant/storage \
    -v "$BACKUP_DIR/$BACKUP_NAME":/backup \
    alpine tar czf /backup/qdrant.tar.gz -C /qdrant/storage . 2>/dev/null || echo "Qdrant backup skipped"

# Backup environment file
cp "$APP_DIR/.env" "$BACKUP_DIR/$BACKUP_NAME/env.backup"

# Compress backup
cd "$BACKUP_DIR"
tar czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

# Remove old backups
find "$BACKUP_DIR" -name "basira-backup-*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_NAME.tar.gz"
