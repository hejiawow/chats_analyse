#!/bin/bash
set -e

SERVER=user@your-server
REMOTE_DIR=/opt/chats_analyse

echo "=== 构建前端 ==="
cd frontend
npm install
npm run build

echo "=== 上传前端产物 ==="
rsync -avz --delete dist/ "$SERVER:$REMOTE_DIR/frontend/dist/"

echo "=== 触发服务器端部署 ==="
ssh "$SERVER" "cd $REMOTE_DIR && bash deploy.sh"

echo "=== 全部完成 ==="
