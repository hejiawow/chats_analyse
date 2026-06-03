# AI会话分析平台

销售聊天记录 AI 分析平台，基于 WeChat 销售对话数据进行智能分析与话术提取。

## 项目概述

AI会话分析平台是一个面向销售培训与分析的智能化系统，通过 AI 技术对销售聊天记录进行多维度分析，包括：

- **转介绍检测**：自动识别销售是否发送了转介绍信息
- **优秀话术提取**：从销售对话中提炼高质量话术（销售话术 + 唤醒话术）
- **优秀成交案例复盘**：分析成功成交案例，生成复盘报告
- **督学跟进合规检测**：检查销售是否满足「60天内跟进11次」的合规标准
- **RAG 问答**：基于话术库的智能问答系统

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI 0.115.0 |
| 异步任务 | Celery 5.4.0 + Redis |
| 数据库 | PostgreSQL 16 + pgvector |
| AI 模型 | LangChain + DashScope (Qwen-plus) |
| 向量检索 | pgvector HNSW 索引 |
| 认证 | JWT + RBAC |
| 前端 | Vue 3 + Vite + Pinia |

## 目录结构

```
hujing-agent-platform/
├── app/                          # 后端应用
│   ├── main.py                   # FastAPI 入口、路由注册、静态文件服务
│   ├── celery_app.py             # Celery 配置
│   ├── config.py                 # 全局配置（已移至根目录）
│   │
│   ├── api/                      # API 路由模块
│   │   ├── auth.py               # 登录认证 API
│   │   ├── users.py              # 用户管理 API
│   │   ├── roles.py              # 角色管理 API
│   │   ├── query.py              # 统计信息查询
│   │   ├── referral_query.py     # 转介绍结果查询
│   │   ├── case_query.py         # 优秀案例结果查询
│   │   ├── sales_journey_query.py# 成交案例复盘查询
│   │   ├── follow_up_query.py    # 督学跟进合规查询
│   │   ├── script_lib.py         # 话术库管理 API
│   │   ├── rag_query.py          # RAG 问答 API
│   │   └── trigger.py            # [已弃用] 旧版触发 API
│   │
│   ├── agents/                   # AI 智能体模块
│   │   ├── registry.py           # Agent 注册中心（装饰器模式）
│   │   ├── referral.py           # 转介绍检测 Agent
│   │   ├── case_extractor.py     # 优秀话术提取 Agent
│   │   ├── sales_journey.py      # 优秀成交案例提取 Agent
│   │   └── follow_up_compliance.py# 督学跟进合规检测 Agent
│   │
│   ├── tasks/                    # Celery 异步任务
│   │   └── analysis.py           # 分析任务 Worker
│   │
│   ├── services/                 # 外部服务封装
│   │   ├── ai_client.py          # LangChain + DashScope 调用
│   │   ├── hujing_api.py         # 虎鲸 CRM API 封装
│   │   ├── embedding.py          # DashScope Embedding 服务
│   │   ├── rag_service.py        # RAG 向量检索 + AI 生成
│   │   ├── cache.py              # Redis 缓存封装
│   │   ├── auth.py               # JWT 认证服务
│   │   ├── html_exporter.py      # HTML 导出服务
│   │   ├── dependencies.py       # FastAPI 依赖注入
│   │   └── datasource/           # 数据源抽象层
│   │       ├── base.py           # 数据源基类
│   │       ├── hujing.py         # 虎鲸数据源实现
│   │       └── manager.py        # 数据源管理器
│   │
│   ├── models/                   # SQLAlchemy 数据模型
│   │   ├── database.py           # 数据库连接配置
│   │   ├── result.py             # 分析结果表（4张表）
│   │   ├── script_lib.py         # 话术库表
│   │   └ auth.py                 # 认证表（users/roles/user_roles）
│   │
│   ├── prompts/                  # AI 提示词模板
│   │   ├── referral_check.md     # 转介绍检测提示词
│   │   ├── case_extraction.md    # 话术提取提示词
│   │   └ sales_journey.md        # 成交案例复盘提示词
│   │
│   └ scripts/                    # 数据库维护脚本（一次性）
│       ├── populate_script_library.py  # 话术库数据填充
│       ├── drop_old_columns.py         # 删除旧字段
│       ├── drop_library_old_columns.py # 删除话术库旧字段
│       ├── add_customer_profile.py     # 添加客户画像字段
│       ├── add_library_customer_profile.py
│       └ add_summary_column.py        # 添加汇总字段
│
├── frontend/                     # Vue 3 前端应用
│   ├── package.json              # npm 配置
│   ├── vite.config.js            # Vite 构建配置
│   ├── login.html                # 登录页面
│   ├── css/
│   │   ├── base.css              # 全局样式
│   │   └ pages/                  # 页面样式
│   ├── js/
│   │   ├── config.js             # API 配置
│   │   ├── api.js                # API 请求封装
│   │   ├── utils.js              # 工具函数
│   │   ├── navigation.js         # 导航控制
│   │   ├── components/           # 公共组件
│   │   └ pages/                  # 页面模块
│   │
│   └ dist/                       # 构建产物（生产环境）
│   └ node_modules/               # npm 依赖
│
├── scripts/                      # 系统脚本
│   ├── init_auth.py              # 初始化用户和角色
│   └── trigger_quality_check.py  # 命令行触发批量质检（支持 crontab）
│
├── documents/                    # [临时文档] 可清理
│
├── config.py                     # 全局配置（环境变量）
├── requirements.txt              # Python 依赖
├── docker-compose.yml            # Docker 部署配置
├── Dockerfile                    # Docker 构建镜像
├── .env.example                  # 环境变量示例
├── CLAUDE.md                     # Claude Code 项目指引
└── README.md                     # 本文件
```

## 核心模块详解

### 1. API 路由模块 (`app/api/`)

| 文件 | 功能 | 主要端点 |
|------|------|----------|
| `auth.py` | 用户认证 | `POST /api/login`, `GET /api/me` |
| `users.py` | 用户管理 | `GET/POST/PUT/DELETE /api/users` |
| `roles.py` | 角色管理 | `GET/POST/PUT/DELETE /api/roles` |
| `query.py` | 统计信息 | `GET /api/stats` |
| `referral_query.py` | 转介绍查询 | `GET /api/referral/*` |
| `case_query.py` | 案例查询 | `GET /api/cases/*` |
| `sales_journey_query.py` | 成交复盘 | `GET /api/sales-journey/*` |
| `follow_up_query.py` | 合规查询 | `GET /api/follow-up/*` |
| `script_lib.py` | 话术库 | `GET/POST /api/scriptlib/*` |
| `rag_query.py` | RAG问答 | `POST /api/rag/query` |
| `trigger.py` | [已弃用] | 被 main.py 中的端点替代 |

**注意**：`app/api/trigger.py` 已被弃用，触发分析 API 已集成到 `main.py` 中：
- `POST /api/trigger` - 执行所有 Agent
- `POST /api/trigger/single` - 执行指定 Agent
- `POST /api/trigger/sales-journey` - 单独执行成交案例提取

### 2. AI 智能体模块 (`app/agents/`)

采用装饰器注册模式，新增 Agent 无需修改其他代码：

```python
@AgentRegistry.register("智能体名称")
def my_agent(user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
    return {"status": "...", "result": {...}}
```

| Agent | 文件 | 功能 | 输出 |
|-------|------|------|------|
| 转介绍检测 | `referral.py` | 检测是否发送转介绍信息 | `ReferralResult` |
| 优秀话术提取 | `case_extractor.py` | 提取销售话术/唤醒话术 | `CaseExtractionResult` |
| 成交案例复盘 | `sales_journey.py` | 分析成功成交案例 | `SalesJourneyResult` |
| 督学合规检测 | `follow_up_compliance.py` | 60天跟进合规检查 | `FollowUpComplianceResult` |

### 3. Celery 任务模块 (`app/tasks/`)

`analysis.py` 核心流程：

1. 从数据源拉取聊天记录
2. 逐个执行已注册的 Agent
3. 将结果保存到对应的数据库表
4. 实时日志写入 Redis（供前端轮询）

**日志存储**：
- `task:logs:{task_id}` - 任务日志列表
- `task:done:{task_id}` - 任务完成标记

### 4. 数据服务模块 (`app/services/`)

| 服务 | 功能 |
|------|------|
| `ai_client.py` | LangChain LLM 调用（DashScope Qwen） |
| `hujing_api.py` | 虎鲸 CRM API 封装（销售列表、好友列表、聊天记录） |
| `embedding.py` | 文本向量化（DashScope text-embedding-v3） |
| `rag_service.py` | RAG 检索 + AI 生成回答 |
| `cache.py` | Redis 缓存封装（销售列表、好友列表缓存） |
| `auth.py` | JWT 签发/验证、密码哈希 |
| `datasource/` | 数据源抽象层（支持扩展多数据源） |

### 5. 数据模型 (`app/models/`)

**分析结果表** (`result.py`)：

| 表名 | 模型 | 用途 |
|------|------|------|
| `referral_results` | `ReferralResult` | 转介绍检测结果 |
| `case_extraction_results` | `CaseExtractionResult` | 话术提取结果（每条话术独立记录） |
| `sales_journey_results` | `SalesJourneyResult` | 成交案例复盘报告 |
| `follow_up_compliance_results` | `FollowUpComplianceResult` | 督学合规检测结果 |

**话术库表** (`script_lib.py`)：

| 表名 | 模型 | 用途 |
|------|------|------|
| `case_script_library` | `CaseScriptLibrary` | 话术库（含 embedding 向量） |

**认证表** (`auth.py`)：

| 表名 | 模型 | 用途 |
|------|------|------|
| `users` | `User` | 用户表 |
| `roles` | `Role` | 角色表（含权限 JSONB） |
| `user_roles` | `UserRole` | 用户-角色关联表 |

### 6. 前端模块 (`frontend/`)

**技术栈**：Vue 3 + Vite + Pinia

**页面模块** (`js/pages/`)：

| 文件 | 页面功能 |
|------|----------|
| `dashboard.js` | 仪表盘（统计概览） |
| `referral.js` | 转介绍检测结果页 |
| `cases.js` | 优秀话术结果页 |
| `salesjourney.js` | 成交案例复盘页 |
| `followup.js` | 督学合规检测页 |
| `scriptlib.js` | 话术库管理页 |
| `rag.js` | RAG 问答页 |
| `agents.js` | Agent 触发页 |

## 请求流程

```
┌─────────────┐    POST /api/trigger     ┌─────────────┐
│   前端      │ ───────────────────────▶ │   FastAPI   │
│   (Vue)     │                          │   (main.py) │
└─────────────┘                          └──────┬──────┘
                                                │
                      ┌─────────────────────────▼─────────────────────────┐
                      │              Celery Worker                         │
                      │              (analysis.py)                         │
                      │                                                    │
                      │  1. 拉取聊天记录 (HujingDataSource)                │
                      │  2. 执行 Agent (AgentRegistry.run_all)            │
                      │     ├── 转介绍检测                                 │
                      │     ├── 优秀话术提取                               │
                      │     ├── 成交案例复盘                               │
                      │     └── 督学合规检测                               │
                      │  3. 保存结果到 PostgreSQL                          │
                      │  4. 日志写入 Redis                                 │
                      └─────────────────────────┬─────────────────────────┘
                                                │
                      ┌─────────────────────────▼─────────────────────────┐
                      │                    PostgreSQL                     │
                      │  ┌──────────────┐  ┌──────────────┐              │
                      │  │ referral_    │  │ case_        │              │
                      │  │ results      │  │ extraction_  │              │
                      │  │              │  │ results      │              │
                      │  └──────────────┘  └──────────────┘              │
                      │  ┌──────────────┐  ┌──────────────┐              │
                      │  │ sales_       │  │ follow_up_   │              │
                      │  │ journey_     │  │ compliance_  │              │
                      │  │ results      │  │ results      │              │
                      │  └──────────────┘  └──────────────┘              │
                      └───────────────────────────────────────────────────┘

前端轮询 GET /api/logs/{task_id} ──▶ Redis ──▶ 实时日志展示
```

## 部署指南

### 环境要求

- Python 3.11+
- Node.js 18+ (前端构建)
- PostgreSQL 16 + pgvector 扩展
- Redis 7+
- Docker & Docker Compose (推荐)

### 配置环境变量

复制 `.env.example` 为 `.env` 并修改：

```bash
# 虎鲸 API（CRM 系统）
HUJING_APP_ID=si_ahyk1221
HUJING_APP_KEY=your_app_key
HUJING_API_BASE_URL=https://hj.ahujiaoyu.com:9029

# AI 服务（阿里云 DashScope）
DASHSCOPE_API_KEY=sk-xxx
AI_MODEL=qwen-plus

# Redis
REDIS_URL=redis://localhost:6379/0

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hujing_agent

# JWT
JWT_SECRET_KEY=your_secret_key
```

### Docker 部署（推荐）

```bash
# 1. 构建并启动所有服务
docker-compose up -d

# 服务包含：
# - redis: Redis 7
# - postgres: PostgreSQL 16 + pgvector
# - api: FastAPI 服务
# - worker: Celery Worker

# 2. 初始化认证数据
docker-compose exec api python scripts/init_auth.py

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f api worker
```

### 本地开发部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 Redis 和 PostgreSQL（可用 Docker）
docker run -d --name redis -p 6379:6379 redis:7-alpine
docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_DB=hujing_agent \
  -e POSTGRES_PASSWORD=postgres \
  pgvector/pgvector:pg16

# 3. 启动 API 服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 启动 Celery Worker
celery -A app.celery_app worker --loglevel=info --concurrency=4

# 5. 初始化认证数据
python scripts/init_auth.py
```

### 前端构建

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build

# 构建产物在 frontend/dist/
# FastAPI 会自动服务静态文件
```

## 数据库初始化

表结构通过 SQLAlchemy 模型自动创建（`init_db()` 在启动时执行）。

如需手动创建表：

```python
from app.models.database import init_db
init_db()
```

### 初始化认证数据

```bash
python scripts/init_auth.py

# 创建默认账号：
# - admin / admin123 (管理员，所有权限)
# - manager / manager123 (主管，读写权限)
```

### 话术库数据填充

```bash
# 从 case_extraction_results 提取高分话术 → 生成 embedding → 入库
python -m app.scripts.populate_script_library
```

## API 文档

启动服务后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 命令行工具

### 批量质检触发 (`scripts/trigger_quality_check.py`)

通过命令行触发批量质检分析（quality_check），任务通过 Celery 异步执行，CLI 提交后立即退出。适合配合系统 crontab 实现定时自动质检。

**使用方式：**

```bash
# 默认：扫描过去 24 小时的聊天记录
python scripts/trigger_quality_check.py

# 指定时间范围
python scripts/trigger_quality_check.py \
  --start-time "2026-06-01 00:00:00" \
  --end-time "2026-06-01 23:59:59"

# 筛选特定销售
python scripts/trigger_quality_check.py --user-id "sales_001"

# 限制分析数量
python scripts/trigger_quality_check.py --limit 100

# 模拟运行（不实际提交）
python scripts/trigger_quality_check.py --dry-run

# 强制提交（跳过锁检查）
python scripts/trigger_quality_check.py --force
```

**参数说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--start-time` | 当前时间 - 24h | 检测开始时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `--end-time` | 当前时间 | 检测结束时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `--user-id` | 全部 | 筛选特定销售 ID |
| `--limit` | 500 | 最大分析数量 |
| `--force` | false | 跳过锁检查，强制提交 |
| `--dry-run` | false | 仅打印参数，不提交任务 |

**防重复机制：**

脚本使用 Redis 分布式锁防止重复提交（锁 TTL 3 小时）。如果上一次任务仍在运行，本次提交会自动跳过（退出码 0）。使用 `--force` 可强制跳过锁检查。

**Crontab 定时调度：**

```bash
# 每小时整点执行一次质检（Docker 部署环境）
0 * * * * cd /opt/chats_analyse && docker compose exec -T worker python scripts/trigger_quality_check.py >> /var/log/quality_check_cron.log 2>&1

# 每 2 小时执行一次
0 */2 * * * cd /opt/chats_analyse && docker compose exec -T worker python scripts/trigger_quality_check.py >> /var/log/quality_check_cron.log 2>&1
```

> 注意：`docker compose exec` 需要 `-T` 标志禁用伪终端分配（crontab 环境必需）。

## 权限说明

| 角色 | 权限 |
|------|------|
| admin | 所有权限 (admin:all) |
| manager | 仪表盘、所有结果页、触发分析、话术库、RAG |
| sales | 仪表盘、优秀案例、话术库、触发分析 |

## 添加新 Agent

1. 在 `app/agents/` 下新建文件
2. 使用装饰器注册：

```python
from app.agents.registry import AgentRegistry

@AgentRegistry.register("新智能体名称")
def my_agent(user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
    # 处理逻辑
    return {"status": "success", "result": {...}}
```

3. 在 `app/tasks/analysis.py` 中添加保存逻辑
4. 新建数据模型（如需要）
5. 新建查询 API（如需要）
6. 新建前端页面（如需要）

## 维护与清理

### 清理无用文件

项目中有一些临时文件和一次性迁移脚本可以清理：

**可删除的文件**：
- `migrate_sales_journey.py` - 已执行的迁移脚本
- `migrate_follow_up_compliance.py` - 已执行的迁移脚本
- `test_sales_journey.py` - 测试脚本
- `app/api/trigger.py` - 已弃用的旧版触发 API
- `app/scripts/` 下大部分迁移脚本 - 一次性使用
- `documents/` 目录下的测试文件（HTML、Excel、SQL 等）

**清理命令**：
```bash
# 删除一次性迁移脚本
rm migrate_sales_journey.py migrate_follow_up_compliance.py test_sales_journey.py

# 删除弃用的 API 文件
rm app/api/trigger.py

# 删除临时文档
rm -rf documents/*.html documents/*.xlsx documents/*.sql documents/*.txt

# 清理 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} +
```

## 许可证

内部项目，仅供阿虎医考内部使用。

## 联系方式

项目维护：阿虎医考技术团队