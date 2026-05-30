#!/bin/bash
set -e

PROJECT_DIR=/opt/chats_analyse
cd "$PROJECT_DIR"

echo "=== 拉取最新代码 ==="
git pull origin main

echo "=== 重建并重启后端容器 ==="
docker compose build api worker
docker compose up -d api worker

echo "=== 清理旧镜像 ==="
docker image prune -f

echo "=== 服务状态 ==="
docker compose ps

echo "=== 部署完成 ==="
