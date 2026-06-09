# AGENTS.md

本文件为 AI 编程助手（Claude Code、Codex、Qoder 等）在本项目中工作时提供指导。

## 项目概述

AI会话分析平台 — 基于 AI 的微信销售会话分析系统。

**技术栈**: FastAPI, Celery, Redis (消息队列/缓存), PostgreSQL + pgvector (异步驱动 asyncpg), LangChain + DashScope (通义千问模型), Vue.js + Vite (前端)

## 常用命令

```bash
# 后端
docker-compose up -d                                        # 启动全部服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   # 仅启动 API (本地开发)
celery -A app.celery_app worker --loglevel=info --concurrency=4  # 启动 Celery Worker
alembic upgrade head                                        # 执行数据库迁移

# 前端
cd frontend && npm install && npm run dev                   # 启动开发服务器
npm run build                                               # 生产构建

# 依赖安装
pip install -r requirements.txt                             # Python 依赖
```

## 系统架构

**请求流程**:
1. 客户端 → `POST /api/trigger` → FastAPI 通过虎鲸 API 验证用户/好友 → 提交 Celery 任务
2. Celery Worker 从虎鲸 API 拉取聊天记录 → 执行已注册的 AI Agent → 将结果保存到 PostgreSQL
3. 客户端轮询 `GET /api/logs/{task_id}` 获取实时日志 (Redis)
4. 查询 API 从 PostgreSQL 读取数据

**目录结构**:
```
app/
├── main.py              # FastAPI 应用入口
├── celery_app.py        # Celery 配置
├── api/                 # API 路由模块
│   ├── trigger.py       # 触发分析任务
│   ├── auth.py          # 认证 (JWT)
│   ├── users.py / roles.py  # 用户/角色管理
│   ├── query.py         # 统计概览
│   ├── referral_query.py    # 转介绍查询
│   ├── case_query.py        # 优秀话术查询
│   ├── sales_journey_query.py  # 成交案例查询
│   ├── follow_up_query.py   # 督学跟进查询
│   ├── quality_check_query.py # 质检结果查询
│   ├── keyword_config.py    # 关键词配置
│   ├── rag_query.py         # RAG 知识库问答
│   ├── script_lib.py        # 话术库管理
│   ├── refund_whitelist_query.py # 退款白名单
│   └── logs.py              # 系统日志查询
├── agents/              # AI Agent (基于装饰器注册)
│   ├── registry.py      # @AgentRegistry.register("名称")
│   ├── referral.py      # 转介绍检测
│   ├── case_extractor.py    # 优秀话术提取
│   ├── sales_journey.py     # 成交案例提取
│   ├── follow_up_compliance.py  # 督学跟进合规检测
│   └── quality_check.py     # 会话质检
├── tasks/               # Celery 任务
│   ├── analysis.py      # 主分析任务 (拉取聊天 → 执行 Agent → 保存结果)
│   ├── batch_quality.py # 批量质检
│   └── log_flush.py     # 日志刷盘
├── services/            # 业务服务层
│   ├── ai_client.py     # AI 调用封装 (call_ai / call_ai_json)
│   ├── ai_semaphore.py  # AI 并发控制 (分布式信号量)
│   ├── hujing_api.py    # 虎鲸 API 封装
│   ├── embedding.py     # 向量嵌入
│   ├── rag_service.py   # RAG 检索增强生成
│   ├── cache.py         # Redis 缓存
│   ├── html_exporter.py # HTML 导出
│   ├── audit_service.py # 审计服务
│   ├── log_service.py   # 日志服务
│   ├── refund_filter.py # 退款过滤
│   └── datasource/      # 多数据源支持
├── models/              # SQLAlchemy ORM 模型
│   ├── result.py        # 分析结果表 (详见下方)
│   ├── auth.py          # 用户/角色/权限
│   ├── script_lib.py    # 话术知识库 (pgvector)
│   └── system_log.py    # 系统日志
├── prompts/             # Markdown 提示词模板
└── middleware/           # 异常处理 + 日志中间件

frontend/                # Vue.js 单页应用
├── src/views/           # 页面组件
├── src/api/             # API 调用层
├── src/router/          # Vue Router 路由
└── src/store/           # Pinia 状态管理

config.py                # Pydantic 配置 (从 .env 加载)
alembic/                 # 数据库迁移脚本
```

## 数据模型 (`app/models/result.py`)

| 模型 | 说明 | 存储方式 |
|------|------|---------|
| `ReferralResult` | 转介绍检测结果 | JSONB |
| `CaseExtractionResult` | 优秀话术提取 (每条话术一行) | 结构化字段 |
| `SalesJourneyResult` | 成交案例分析 | JSONB |
| `FollowUpComplianceResult` | 督学跟进合规检测 (滑动窗口) | JSONB |
| `QualityCheckTask` | 质检任务 | 结构化字段 |
| `QualityCheckResult` | 质检结果 | JSONB |
| `QualityCheckDetail` | 质检明细 | JSONB |
| `QualityCheckModificationLog` | 质检修改审计日志 | JSONB |
| `RiskKeyword` | 风险关键词配置 | 结构化字段 |
| `RefundWhitelistPattern` | 退款白名单模式 | 结构化字段 |

**其他模型**:
- `app/models/auth.py`: `User`、`Role`、`UserRole` — RBAC 权限系统
- `app/models/script_lib.py`: `CaseScriptLibrary` — 话术知识库 (pgvector Vector(1024) + HNSW 索引)
- `app/models/system_log.py`: `SystemLog` — 统一日志表 (API 访问日志 / 审计日志 / 错误日志)

## 新增 Agent 步骤

1. 创建 `app/agents/<name>.py`
2. 使用装饰器注册：`@AgentRegistry.register("Agent名称")`
3. 函数签名：`(user_id: str, friend_id: int, chat_records: list) -> dict`
4. 返回值至少包含 `{"status": "..."}`
5. 在 `app/agents/__init__.py` 中导入
6. 在 `app/tasks/analysis.py` 中添加保存逻辑
7. 如需查询接口，在 `app/api/` 中添加路由

## 外部集成

- **虎鲸 API** (`app/services/hujing_api.py`): 内部 CRM 系统，用于获取销售聊天记录、好友列表、用户信息
- **DashScope** (`app/services/ai_client.py`): 阿里云大模型 API (通义千问)，通过 `call_ai()` / `call_ai_json()` 调用
- **Embedding** (`app/services/embedding.py`): 文本向量化服务，用于 RAG 检索

## 编码规范

- **Python**: UTF-8 编码，注释以中文为主
- **数据库**: PostgreSQL，异步操作使用 asyncpg，同步操作使用 psycopg2
- **时区**: 统一使用东八区 (Asia/Shanghai)，通过 `config.now_shanghai()` 获取当前时间
- **Alembic**: 迁移脚本位于 `alembic/versions/`，注意维护 `down_revision` 链的正确性
  - **命名规范**: `{YYYYMMDD}_{序号}_{描述}.py`，例如 `20260609_01_add_retry_count.py`
    - `YYYYMMDD`: 日期前缀，确保时间顺序
    - `序号`: 同一天的迁移用两位数字递增（01, 02, 03...）
    - `描述`: 小写下划线分隔，简洁描述变更内容
  - **revision ID**: 使用 `{YYYYMMDD}_{序号}` 格式，例如 `20260609_01`
  - **分支管理**: 新功能分支应基于主分支最新版本设置 `down_revision`，避免分支交叉
- **前端**: Vue 3 Composition API + Pinia + Vue Router


## TDD 强制规范（Test-Driven Development）

**铁律：没有失败的测试，就不写生产代码。**

所有 AI Agent 在实现新功能、修复 Bug、重构或行为变更时，必须严格遵循 TDD 流程。违反以下规则等同于违反规范精神。

### Red-Green-Refactor 循环

1. **RED — 先写失败的测试**
   - 每次只写一个最小化的测试，描述期望行为
   - 测试名必须清晰描述行为（禁止 `test('test1')`）
   - 一个测试只验证一个行为（名称中出现 "and" 就拆分）
   - 优先使用真实代码，仅在不可避免时使用 mock

2. **验证 RED — 必须看到测试失败（不可跳过）**
   - 确认测试失败（不是报错），且失败原因符合预期（功能缺失而非拼写错误）
   - 如果测试直接通过 → 说明在测试已有行为，需修正测试
   - 如果测试报错 → 先修复错误，重新运行直到正确失败

3. **GREEN — 写最少的代码让测试通过**
   - 只写刚好通过测试的代码，不添加额外功能、不重构其他代码、不"顺手改进"
   - 禁止过度设计（不预留参数、不添加未被测试要求的选项）

4. **验证 GREEN — 必须看到测试通过（不可跳过）**
   - 确认当前测试通过，且所有已有测试仍然通过
   - 输出干净（无错误、无警告）
   - 测试失败 → 修改代码而非测试

5. **REFACTOR — 仅在 GREEN 之后清理**
   - 消除重复、改善命名、提取辅助函数
   - 保持所有测试绿色，不添加新行为

6. **循环**：下一个功能 → 下一个失败测试 → 重复

### 禁止行为

| 红旗行为 | 正确做法 |
|----------|----------|
| 先写代码再补测试 | 删除代码，从测试重新开始 |
| 测试写完直接通过 | 测试必须失败过才有意义 |
| "太简单不需要测试" | 简单代码也会出 bug，测试只需 30 秒 |
| "之后再补测试" | 后补测试直接通过，证明不了任何事 |
| 保留先写的代码作为"参考" | 删除就是删除，不留参考 |
| 手动测试过了就行 | 手动测试是临时的，无法回归 |
| "就这一次跳过 TDD" | 合理化借口，每次都这样想 |
| 修 Bug 不加测试 | Bug 修复必须先写复现测试 |

### 完成检查清单

标记任务完成前必须确认：
- [ ] 每个新函数/方法都有对应测试
- [ ] 每个测试都先看到了失败
- [ ] 每个测试因预期原因失败（功能缺失，非拼写错误）
- [ ] 只写了让测试通过的最少代码
- [ ] 所有测试通过，输出干净
- [ ] 边界情况和错误场景已覆盖

### Bug 修复流程

发现 Bug → 写复现测试（RED）→ 验证失败 → 写最少修复代码（GREEN）→ 验证通过 → 重构 → 测试同时证明修复有效且防止回归。

**永远不要在没有测试的情况下修复 Bug。**


## 卡帕斯的4条AI编程原则

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
