# -*- coding: utf-8 -*-
"""FastAPI 应用入口"""
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.models.database import init_db, async_engine
from app.api import query, referral_query, case_query, script_lib, rag_query, sales_journey_query, follow_up_query, auth, users, roles, quality_check_query, keyword_config
from app.tasks.analysis import run_analysis, get_task_logs, clear_task_logs, is_task_done
from app.models.result import SalesJourneyResult  # ensure table creation
from app.services.hujing_api import (
    resolve_user_id_by_name,
    resolve_friend_id_by_phone,
    resolve_friend_by_identifier,
    get_friends_list,
    get_friends_batch,
    get_all_sales,
    find_sales_by_name_with_friend,
    get_department_tree,
    find_sales_by_department_and_name,
)
from app.tasks.batch_quality import run_batch_quality_check, get_batch_progress, cancel_batch_task, run_batch_quality_check_by_messages
from app.services.datasource.manager import DataSourceManager
from app.services.dependencies import require_permission, require_auth, get_current_user

logger = logging.getLogger(__name__)


class TriggerRequest(BaseModel):
    task_id: str | None = None
    datasource: str = "hujing"  # 数据源标识
    agent: str | None = None  # 'all', 'referral', 'case', 'journey'
    user_id: str | None = None
    user_name: str | None = None
    friend_id: int | None = None
    friend_phone: str | None = None
    friend_wx_id: str | None = None
    friend_alias: str | None = None
    user_wx_id: str | None = None
    friend_nick: str | None = None


def _resolve_ids(req: TriggerRequest) -> tuple[str, int]:
    # 获取数据源实例
    ds = DataSourceManager.get(req.datasource)
    if not ds:
        raise HTTPException(status_code=400, detail=f"未知数据源: {req.datasource}")

    user_id = req.user_id
    if not user_id and req.user_name:
        user_id = ds.resolve_user_id_by_name(req.user_name)
        if not user_id:
            raise HTTPException(status_code=404, detail=f"未找到姓名为「{req.user_name}」的销售")
    if not user_id:
        raise HTTPException(status_code=400, detail="需提供 user_id 或 user_name")

    friend_id = req.friend_id
    if not friend_id:
        if req.friend_phone:
            fid, finfo = ds.resolve_friend_by_identifier(user_id, req.friend_phone)
            if fid:
                friend_id = fid
                if not req.friend_nick:
                    req.friend_nick = finfo.get("nick") or finfo.get("remark") or req.friend_nick
        if not friend_id and req.friend_wx_id:
            fid, finfo = ds.resolve_friend_by_identifier(user_id, req.friend_wx_id)
            if fid:
                friend_id = fid
                if not req.friend_nick:
                    req.friend_nick = finfo.get("nick") or finfo.get("remark") or req.friend_nick
        if not friend_id and req.friend_alias:
            fid, finfo = ds.resolve_friend_by_identifier(user_id, req.friend_alias)
            if fid:
                friend_id = fid
                if not req.friend_nick:
                    req.friend_nick = finfo.get("nick") or finfo.get("remark") or req.friend_nick
        if not friend_id:
            raise HTTPException(status_code=404, detail=f"未找到好友：好友ID、手机号、微信号、客户别名均无法匹配到对应好友")

    return user_id, friend_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库表
    init_db()
    yield
    # 关闭时释放连接池
    await async_engine.dispose()


app = FastAPI(
    title="AI会话分析平台",
    description="销售聊天记录 AI 分析平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api", tags=["认证"])
app.include_router(users.router, prefix="/api", tags=["用户管理"])
app.include_router(roles.router, prefix="/api", tags=["角色管理"])
app.include_router(query.router, prefix="/api", tags=["统计信息"])
app.include_router(referral_query.router, prefix="/api", tags=["转介绍结果"])
app.include_router(case_query.router, prefix="/api", tags=["优秀案例结果"])
app.include_router(sales_journey_query.router, prefix="/api", tags=["成交案例复盘"])
app.include_router(follow_up_query.router, prefix="/api", tags=["督学跟进合规"])
app.include_router(script_lib.router, prefix="/api", tags=["话术库"])
app.include_router(rag_query.router, prefix="/api", tags=["RAG问答"])
app.include_router(quality_check_query.router, prefix="/api", tags=["质检检测"])
app.include_router(keyword_config.router, prefix="/api", tags=["关键词配置"])


@app.post("/api/trigger")
async def trigger_analysis(
    req: TriggerRequest,
    current_user: dict = Depends(require_permission("write:trigger")),
):
    """触发分析 — 提交到 Celery 异步执行（3 个 Agent）"""
    task_id = req.task_id or str(uuid.uuid4())
    try:
        # === 场景：姓名 + 标识（手机号/微信号/客户别名），需要处理重名 ===
        if req.user_name and not req.user_id and not req.friend_id:
            identifier = req.friend_phone or req.friend_wx_id or req.friend_alias
            if identifier:
                ds = DataSourceManager.get(req.datasource)
                if not ds:
                    raise HTTPException(status_code=400, detail=f"未知数据源: {req.datasource}")
                matches = find_sales_by_name_with_friend(req.user_name, identifier)
                if not matches:
                    detail = f"未找到姓名为「{req.user_name}」的销售拥有标识为「{identifier}」的好友"
                    raise HTTPException(status_code=404, detail=detail)
                if len(matches) > 1:
                    return {
                        "task_id": task_id,
                        "duplicate": True,
                        "message": f"找到 {len(matches)} 个同名销售，请选择对应的销售",
                        "options": matches,
                    }
                # 唯一匹配，继续往下走
                req.user_id = matches[0]["user_id"]
                req.friend_id = matches[0]["friend_id"]
                if not req.friend_nick:
                    req.friend_nick = matches[0]["friend_nick"]
                if not req.friend_wx_id:
                    req.friend_wx_id = matches[0]["friend_wx_id"]

        # === 正常解析 ===
        user_id, friend_id = _resolve_ids(req)

        # 提交到 Celery 异步执行
        run_analysis.delay(
            task_id=task_id,
            user_id=user_id,
            friend_id=friend_id,
            user_wx_id=req.user_wx_id,
            friend_wx_id=req.friend_wx_id,
            friend_nick=req.friend_nick,
            agent="all",  # 执行所有 Agent
            datasource=req.datasource,  # 传递数据源
        )

        return {
            "task_id": task_id,
            "message": "分析任务已提交，正在后台执行中...",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="分析失败，请稍后重试")


@app.get("/api/datasources")
async def get_datasources(current_user: dict = Depends(require_auth)):
    """获取所有可用的数据源列表"""
    sources = DataSourceManager.list_all_with_info()
    return {"datasources": sources}


@app.post("/api/trigger/single")
async def trigger_single_agent(
    req: TriggerRequest,
    current_user: dict = Depends(require_permission("write:trigger")),
):
    """触发智能体分析（支持单个或多个，逗号分隔）— 提交到 Celery 异步执行"""
    task_id = req.task_id or str(uuid.uuid4())

    agent_map = {
        "referral": "转介绍检测",
        "case": "优秀话术提取",
        "journey": "优秀成交案例提取",
        "follow_up": "督学跟进合规检测",
    }

    # 支持逗号分隔的多个智能体
    if not req.agent:
        raise HTTPException(status_code=400, detail="未指定智能体")

    agent_names = []
    for agent in req.agent.split(','):
        agent = agent.strip()
        if agent not in agent_map:
            raise HTTPException(status_code=400, detail=f"无效的智能体: {agent}")
        agent_names.append(agent_map[agent])

    try:
        user_id, friend_id = _resolve_ids(req)

        # 提交到 Celery 异步执行
        run_analysis.delay(
            task_id=task_id,
            user_id=user_id,
            friend_id=friend_id,
            user_wx_id=req.user_wx_id,
            friend_wx_id=req.friend_wx_id,
            friend_nick=req.friend_nick,
            agent=req.agent,  # 传递原始逗号分隔的字符串
            datasource=req.datasource,  # 传递数据源
        )

        return {
            "task_id": task_id,
            "message": f"[{' / '.join(agent_names)}] 分析任务已提交，正在后台执行中...",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="分析失败，请稍后重试")


@app.post("/api/trigger/sales-journey")
async def trigger_sales_journey(
    req: TriggerRequest,
    current_user: dict = Depends(require_permission("write:trigger")),
):
    """单独触发「优秀成交案例提取」Agent — 提交到 Celery 异步执行"""
    task_id = req.task_id or str(uuid.uuid4())
    try:
        user_id, friend_id = _resolve_ids(req)

        # 提交到 Celery 异步执行
        run_analysis.delay(
            task_id=task_id,
            user_id=user_id,
            friend_id=friend_id,
            user_wx_id=req.user_wx_id,
            friend_wx_id=req.friend_wx_id,
            friend_nick=req.friend_nick,
            agent="journey",  # 只执行优秀成交案例提取
        )

        return {
            "task_id": task_id,
            "message": "[优秀成交案例提取] 分析任务已提交，正在后台执行中...",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="分析失败，请稍后重试")


@app.post("/api/trigger/quality-check")
async def trigger_quality_check(
    req: TriggerRequest,
    current_user: dict = Depends(require_permission("write:trigger")),
):
    """质检专用触发接口：自动计算昨天此时到今天此时，执行关键词检测 + AI分析"""
    task_id = req.task_id or str(uuid.uuid4())
    try:
        user_id, friend_id = _resolve_ids(req)

        # 计算时间范围：昨天此时到今天此时
        now = datetime.now()
        yesterday_same_time = now - timedelta(hours=24)
        start_time = yesterday_same_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")

        # 提交到 Celery 异步执行
        run_analysis.delay(
            task_id=task_id,
            user_id=user_id,
            friend_id=friend_id,
            user_wx_id=req.user_wx_id,
            friend_wx_id=req.friend_wx_id,
            friend_nick=req.friend_nick,
            agent="quality_check",
            datasource=req.datasource,
            start_time=start_time,
            end_time=end_time,
        )

        return {
            "task_id": task_id,
            "time_range": {"start": start_time, "end": end_time},
            "message": f"[质检检测] 分析任务已提交，时间范围：{start_time} 至 {end_time}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="分析失败，请稍后重试")


class BatchQualityCheckRequest(BaseModel):
    start_time: str | None = None  # 开始时间，默认昨天此时
    end_time: str | None = None  # 结束时间，默认今天此时
    user_id: str | None = None  # 可选，筛选特定销售
    limit: int = 500  # 最大分析数量


@app.post("/api/trigger/batch-quality-check")
async def trigger_batch_quality_check(
    req: BatchQualityCheckRequest,
    current_user: dict = Depends(require_permission("write:trigger")),
):
    """批量质检触发接口：分析指定时间范围内有聊天记录的聊天对"""
    task_id = str(uuid.uuid4())

    # 计算时间范围：默认昨天此时到今天此时
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    start_time = req.start_time or yesterday.strftime("%Y-%m-%d %H:%M:%S")
    end_time = req.end_time or now.strftime("%Y-%m-%d %H:%M:%S")

    # 提交批量质检任务
    run_batch_quality_check.delay(
        batch_task_id=task_id,
        start_time=start_time,
        end_time=end_time,
        user_id_filter=req.user_id,
        limit=req.limit,
    )

    return {
        "task_id": task_id,
        "time_range": {"start": start_time, "end": end_time},
        "message": f"批量质检已启动，时间范围：{start_time} 至 {end_time}",
    }


@app.post("/api/trigger/batch-quality-check-by-messages")
async def trigger_batch_quality_check_by_messages(
    req: BatchQualityCheckRequest,
    current_user: dict = Depends(require_permission("write:trigger")),
):
    """新批量质检触发接口：基于聊天记录的关键词匹配

    流程：
    1. 获取时间范围内所有聊天记录
    2. 对每条聊天记录进行关键词匹配
    3. 提取匹配到的销售ID和好友ID，去重
    4. 对去重后的销售-好友对进行质检分析
    """
    task_id = str(uuid.uuid4())

    # 计算时间范围：默认昨天此时到今天此时
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    start_time = req.start_time or yesterday.strftime("%Y-%m-%d %H:%M:%S")
    end_time = req.end_time or now.strftime("%Y-%m-%d %H:%M:%S")

    # 提交新批量质检任务（基于聊天记录）
    run_batch_quality_check_by_messages.delay(
        batch_task_id=task_id,
        start_time=start_time,
        end_time=end_time,
        user_id_filter=req.user_id,
        limit=req.limit,
    )

    return {
        "task_id": task_id,
        "time_range": {"start": start_time, "end": end_time},
        "message": f"新批量质检已启动（基于聊天记录关键词匹配），时间范围：{start_time} 至 {end_time}",
    }


@app.get("/api/batch-quality-check/{task_id}/progress")
async def get_batch_quality_check_progress(task_id: str, current_user: dict = Depends(require_auth)):
    """获取批量质检进度"""
    progress = get_batch_progress(task_id)
    return {"task_id": task_id, **progress}


@app.get("/api/batch-quality-check/{task_id}/errors")
async def get_batch_quality_check_errors(task_id: str, current_user: dict = Depends(require_auth)):
    """获取批量质检失败详情"""
    from app.tasks.batch_quality import get_batch_errors
    errors = get_batch_errors(task_id)
    return {"task_id": task_id, "errors": errors}


@app.post("/api/batch-quality-check/{task_id}/cancel")
async def cancel_batch_quality_check(task_id: str, current_user: dict = Depends(require_permission("write:trigger"))):
    """取消批量质检任务"""
    cancel_batch_task(task_id)
    return {"task_id": task_id, "status": "cancelling", "message": "任务取消请求已提交"}


@app.get("/api/logs/{task_id}")
async def get_analysis_logs(task_id: str, current_user: dict = Depends(require_auth)):
    """轮询获取分析任务的实时日志"""
    return {"task_id": task_id, "logs": get_task_logs(task_id), "done": is_task_done(task_id)}


@app.post("/api/logs/{task_id}/clear")
async def clear_analysis_logs(task_id: str, current_user: dict = Depends(require_permission("write:trigger"))):
    """清理指定任务的日志"""
    clear_task_logs(task_id)
    return {"status": "ok"}


@app.get("/api/sales")
async def get_sales_list(current_user: dict = Depends(require_auth)):
    """获取销售列表（带缓存）"""
    sales = get_all_sales()
    return {"data": sales}


@app.get("/api/friends/{user_id}")
async def get_friends_by_user(user_id: str, current_user: dict = Depends(require_auth)):
    """获取指定销售的好友列表（带缓存）"""
    friends = get_friends_list(user_id)
    return {"data": friends}


class BatchFriendsRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=100, description="销售ID列表，最多100个")


@app.post("/api/friends/batch")
async def get_friends_batch_endpoint(
    req: BatchFriendsRequest,
    current_user: dict = Depends(require_auth),
):
    """批量获取多个销售的好友列表"""
    friends_map = get_friends_batch(req.user_ids)
    return {"data": friends_map}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# 静态文件服务（Vue 构建产物）
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(full_path: str):
    """SPA fallback — 提供 Vue 构建的 index.html"""
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return HTMLResponse(content=index.read_text(encoding="utf-8"))
    # 开发模式：返回简单提示
    return HTMLResponse(content="""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px">
    <h1>AI会话分析平台</h1>
    <p>前端尚未构建，请使用以下命令启动开发服务器：</p>
    <pre>cd frontend && npm install && npm run dev</pre>
    <p>或构建生产版本：</p>
    <pre>cd frontend && npm run build</pre>
    <p>API 文档：<a href="/docs">/docs</a></p>
    </body></html>
    """)
