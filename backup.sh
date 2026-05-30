#!/bin/bash
set -e

BACKUP_DIR=/data/backups
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hujing_agent_$TIMESTAMP.sql.gz"

cd /opt/chats_analyse

echo "=== 备份数据库 ==="
docker-compose exec -T postgres pg_dump -U postgres hujing_agent | gzip > "$BACKUP_FILE"

echo "=== 备份完成: $BACKUP_FILE ==="
echo "文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"

# 保留最近 30 天备份
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
