# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI会话分析平台 — a sales chat analysis platform that uses AI to analyze WeChat sales conversations. Built with FastAPI + Celery + PostgreSQL (pgvector) + Redis.

## Key Commands

```bash
# Start all services (API + Worker + Redis + Postgres)
docker-compose up -d

# Start API only (local dev)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker (local dev)
celery -A app.celery_app worker --loglevel=info --concurrency=4

# Install dependencies
pip install -r requirements.txt
```

## Architecture

**Tech Stack**: FastAPI, Celery, Redis (broker/cache), PostgreSQL + pgvector (async via asyncpg), LangChain + DashScope (Qwen models)

**Request Flow**:
1. Client calls `POST /api/trigger` → FastAPI validates user/friend via 虎鲸 API → submits Celery task
2. Celery worker pulls chat records from 虎鲸 API → runs registered AI Agents → saves results to PostgreSQL
3. Client polls `GET /api/logs/{task_id}` for real-time logs (stored in Redis)
4. Query APIs (`/api/stats`, `/api/referral/*`, etc.) read from PostgreSQL

**Directory Structure**:
- `app/main.py` — FastAPI app, all HTTP routes
- `app/api/` — API routers (query, referral_query, case_query, sales_journey_query, follow_up_query, rag_query, script_lib, trigger)
- `app/tasks/analysis.py` — Celery task: fetch chats → run agents → save results
- `app/agents/` — AI agents with decorator-based registry (`@AgentRegistry.register("名称")`)
  - `referral.py` — 转介绍检测 (referral detection)
  - `case_extractor.py` — 优秀话术提取 (script extraction)
  - `sales_journey.py` — 优秀成交案例提取 (sales journey analysis)
  - `follow_up_compliance.py` — 督学跟进合规检测 (compliance check)
- `app/services/` — External integrations (hujing_api, ai_client, rag_service, embedding, cache, html_exporter)
- `app/models/` — SQLAlchemy models (result.py has all result tables)
- `app/prompts/` — Markdown prompt templates
- `config.py` — Pydantic settings (loaded from `.env`)

**Adding a New Agent**:
1. Create new file in `app/agents/`
2. Decorate with `@AgentRegistry.register("Agent名称")`
3. Function signature: `(user_id: str, friend_id: int, chat_records: list) -> dict`
4. Return dict with at least `{"status": "..."}`
5. Import the module somewhere (already done via `import app.agents` in analysis.py)
6. Add save logic in `app/tasks/analysis.py` for persisting results
7. Add a query API if needed

**Data Models** (in `app/models/result.py`):
- `ReferralResult` — referral detection results (JSONB)
- `CaseExtractionResult` — individual script entries (one row per script)
- `SalesJourneyResult` — sales journey analysis (JSONB)
- `FollowUpComplianceResult` — compliance check with sliding window analysis

**AI Integration**: Uses DashScope (阿里云) via LangChain. `app/services/ai_client.py` provides `call_ai()` and `call_ai_json()`. Embedding uses `app/services/embedding.py`.

**虎鲸 API**: Internal CRM API for fetching sales chat records, friend lists, and user info. See `app/services/hujing_api.py`.
