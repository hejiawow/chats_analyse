# 生产部署指南

## 架构概览

```
┌────────────────────── ECS 宿主机 ──────────────────────┐
│                                                        │
│  Nginx (systemd) ─── /opt/chats_analyse/frontend/dist  │
│       │                                                │
│       └── proxy_pass ──→ 127.0.0.1:8010               │
│                                                        │
├──────────────────── Docker 容器 ────────────────────────┤
│                                                        │
│  api     (uvicorn, :8000 → 宿主机 :8010)               │
│  worker  (celery)                                      │
│  postgres ── volume ──→ /data/pg_data (宿主机磁盘)     │
│  redis    ── volume ──→ /data/redis   (宿主机磁盘)     │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**部署策略**：前端本地构建 + rsync 上传，后端 Docker 部署，数据库 volume 映射宿主机磁盘保证数据持久化。

## 环境要求

| 组件 | 版本 | 部署方式 |
|------|------|----------|
| Docker | 20+ | 宿主机 |
| Docker Compose | v2+ | 宿主机 |
| Nginx | 1.24+ | 宿主机 |
| Node.js | 18+ | 本地开发机（构建前端） |
| Python | 3.11+ | Docker 容器内 |
| PostgreSQL | 16 + pgvector | Docker 容器 |
| Redis | 7+ | Docker 容器 |

## 1. 服务器初始化

### 1.1 安装 Docker

```bash
curl -fsSL https://get.docker.com | bash
sudo systemctl enable docker
```

### 1.2 创建数据目录

```bash
sudo mkdir -p /data/pg_data /data/redis /data/backups
# postgres 容器内 uid=999, redis 容器内 uid=999
sudo chown -R 999:999 /data/pg_data /data/redis
```

### 1.3 部署代码

```bash
sudo mkdir -p /opt/chats_analyse
cd /opt/chats_analyse
git clone <repo-url> .
```

### 1.4 配置环境变量

```bash
cp .env.example .env
vim .env
```

```env
# === 虎鲸 API ===
HUJING_APP_ID=your_app_id
HUJING_APP_KEY=your_app_key
HUJING_API_BASE_URL=https://hj.ahujiaoyu.com:9029

# === 虎鲸 Chat API（批量质检）===
HUJING_CHAT_API_URL=http://192.168.20.217:8006
HUJING_CHAT_API_KEY=your_chat_api_key

# === AI (DashScope) ===
DASHSCOPE_API_KEY=sk-your-api-key
AI_MODEL=qwen-plus

# === Redis（容器内通过服务名访问）===
REDIS_URL=redis://:your_redis_password@redis:6379/0

# === PostgreSQL（容器内通过服务名访问）===
DATABASE_URL=postgresql+asyncpg://postgres:strong_password@postgres:5432/hujing_agent
DATABASE_URL_SYNC=postgresql://postgres:strong_password@postgres:5432/hujing_agent

# === JWT ===
JWT_SECRET_KEY=（使用下方命令生成）
```

生成 JWT 密钥和数据库密码：

```bash
openssl rand -hex 32
```

> **注意**：`.env` 中 Redis/PostgreSQL 地址用 Docker 服务名（`redis`/`postgres`），不是 `localhost`。如需在宿主机运行脚本，用映射端口 `localhost:6370` / `localhost:5430`。

### 1.5 保护环境变量

```bash
chmod 600 /opt/chats_analyse/.env
```

## 2. 启动后端服务

```bash
cd /opt/chats_analyse
docker-compose up -d
```

首次部署初始化数据库：

```bash
docker-compose exec api python scripts/db_create.py --new-db hujing_agent --init-data
```

默认管理员：`admin` / `admin123`，**上线后必须修改密码**。

验证服务状态：

```bash
docker-compose ps
curl http://127.0.0.1:8010/docs
```

## 3. 前端构建 & 部署

前端在**本地开发机**构建，rsync 上传到服务器。

### 3.1 本地构建

```bash
cd frontend
npm install
npm run build
# 产物在 frontend/dist/
```

### 3.2 上传到服务器

```bash
rsync -avz --delete dist/ user@your-server:/opt/chats_analyse/frontend/dist/
```

> `--delete` 保证服务器上没有旧版本残留文件。

## 4. Nginx 配置

### 4.1 安装 Nginx

```bash
sudo apt update && sudo apt install -y nginx
```

### 4.2 配置站点

```bash
sudo vim /etc/nginx/conf.d/chats_analyse.conf
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为实际域名或 IP

    # 前端静态资源
    root /opt/chats_analyse/frontend/dist;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API — 代理到 Docker FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 长连接支持（SSE / 轮询场景）
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 静态资源长缓存（Vite 构建的 JS/CSS 带 hash）
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
    }
}
```

### 4.3 启动 Nginx

```bash
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx
```

### 4.4 HTTPS（推荐）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 5. 部署脚本

### 5.1 服务器端 — deploy.sh

放在服务器 `/opt/chats_analyse/deploy.sh`，负责拉取代码 + 重建后端容器。

```bash
#!/bin/bash
set -e

PROJECT_DIR=/opt/chats_analyse
cd "$PROJECT_DIR"

echo "=== 拉取最新代码 ==="
git pull origin main

echo "=== 重建并重启后端容器 ==="
docker-compose build api worker
docker-compose up -d api worker

echo "=== 清理旧镜像 ==="
docker image prune -f

echo "=== 服务状态 ==="
docker-compose ps

echo "=== 部署完成 ==="
```

```bash
chmod +x /opt/chats_analyse/deploy.sh
```

### 5.2 本地端 — deploy-local.sh

放在本地项目根目录，负责构建前端 + 上传 + 触发服务器部署。

```bash
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
```

```bash
chmod +x deploy-local.sh
```

**日常部署只需一条命令**：

```bash
./deploy-local.sh
```

### 5.3 数据库备份 — backup.sh

放在服务器，crontab 定时执行。

```bash
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
```

```bash
chmod +x /opt/chats_analyse/backup.sh
```

设置定时任务（每天凌晨 2 点备份）：

```bash
sudo crontab -e
# 添加：
0 2 * * * /opt/chats_analyse/backup.sh >> /data/backups/backup.log 2>&1
```

### 5.4 数据库恢复

```bash
gunzip -c /data/backups/hujing_agent_20260530_020000.sql.gz | \
  docker-compose exec -T postgres psql -U postgres hujing_agent
```

## 6. 常用运维命令

```bash
# 查看服务状态
docker-compose ps

# 查看后端日志
docker-compose logs -f api
docker-compose logs -f worker

# 重启后端（数据库/Redis 不受影响）
docker-compose restart api worker

# 进入 API 容器调试
docker-compose exec api bash

# 查看 Redis 连接
docker-compose exec redis redis-cli -a your_redis_password ping

# 查看数据库
docker-compose exec postgres psql -U postgres hujing_agent -c "\dt"

# 更新单个服务（如只改了后端代码）
docker-compose build api worker && docker-compose up -d api worker
```

## 7. 验证部署

```bash
# 检查 API
curl http://127.0.0.1:8010/docs

# 检查 Nginx + 前端
curl -I http://your-domain.com

# 检查 HTTPS
curl -I https://your-domain.com

# 检查 API 通过 Nginx 代理
curl http://your-domain.com/api/health 2>/dev/null || echo "无 health 端点，检查 /api/docs"
```

## 8. 常见问题

### Q: 前端页面空白，控制台 404

Nginx 未配置 SPA fallback，确认 `try_files $uri $uri/ /index.html;` 存在。

### Q: API 请求 502 Bad Gateway

1. 检查 API 容器运行：`docker-compose ps api`
2. 检查端口匹配：Nginx `proxy_pass` 为 `http://127.0.0.1:8010`，docker-compose 映射为 `127.0.0.1:8010:8000`
3. 查看 API 日志：`docker-compose logs api`

### Q: Celery 任务不执行

1. 检查 Worker 容器：`docker-compose ps worker`
2. 检查 Redis 连接：`docker-compose exec redis redis-cli -a your_redis_password ping`
3. 查看 Worker 日志：`docker-compose logs worker`

### Q: 数据库连接失败

1. 检查 Postgres 容器：`docker-compose ps postgres`
2. 检查 `.env` 中地址是否用 Docker 服务名：`@postgres:5432`（不是 `@localhost`）
3. 检查 pgvector 扩展：`docker-compose exec postgres psql -U postgres hujing_agent -c "SELECT extname FROM pg_extension WHERE extname='vector';"`

### Q: 前端构建后 API 请求失败

生产环境不走 Vite 代理，所有 `/api/` 请求由 Nginx 反向代理到后端。确认 Nginx `location /api/` 中 `proxy_pass` 地址正确。

### Q: 数据库数据会丢失吗

不会。PostgreSQL 和 Redis 的数据文件通过 volume 映射到宿主机 `/data/pg_data` 和 `/data/redis`，容器重建不影响数据。Redis 启用了 AOF 持久化（`--appendonly yes`），PostgreSQL 默认使用 WAL 日志。
