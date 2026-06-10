# -*- coding: utf-8 -*-
"""质检二次审查 API"""
import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_
from app.models.database import async_session
from app.models.result import QualityCheckResult, QualityReviewResult, QualityCheckDetail, QualityCheckTask
from app.services.dependencies import require_permission
from app.agents.quality_review import quality_review_agent
from app.services.hujing_api import get_chat_records_for_quality_check
from app.services.cache import get_redis
from app.tasks.quality_review import batch_quality_review_task
from app.services.quality_review_query import pending_review_conditions
from config import now_shanghai, to_naive_shanghai

router = APIRouter()

# Redis 分布式锁 key
_AUTO_BATCH_LOCK_KEY = "quality_review:auto_batch_lock"
_AUTO_BATCH_LOCK_TTL = 300  # 5分钟内只允许一个 batch


@router.post("/quality-review/auto-batch")
async def auto_batch_quality_review(
    current_user: dict = Depends(require_permission("write:quality_review")),
):
    """一键审查所有未审查的高中风险结果

    流程：
    1. Redis 分布式锁防并发
    2. 查询所有 has_secondary_review=False 且有效风险等级为 high/medium 的结果
    3. 生成批次号（UUID）
    4. 提交Celery异步任务
    5. 返回批次号和总数
    """
    # 1. Redis 分布式锁防并发
    redis_client = get_redis()
    if redis_client:
        acquired = redis_client.set(_AUTO_BATCH_LOCK_KEY, "1", nx=True, ex=_AUTO_BATCH_LOCK_TTL)
        if not acquired:
            raise HTTPException(status_code=409, detail="已有审查任务正在执行，请稍后重试")

    try:
        async with async_session() as session:
            # 2. 查询所有符合条件的未审查结果ID
            conditions = pending_review_conditions()
            stmt = select(QualityCheckResult.id).where(*conditions)
            result = await session.execute(stmt)
            result_ids = [row[0] for row in result.all()]

        if not result_ids:
            if redis_client:
                redis_client.delete(_AUTO_BATCH_LOCK_KEY)
            raise HTTPException(status_code=404, detail="暂无未审查的高中风险结果")

        # 3. 生成批次号
        batch_id = str(uuid.uuid4())
    except HTTPException:
        raise
    except Exception:
        # 查询阶段出错，释放锁允许重试
        if redis_client:
            redis_client.delete(_AUTO_BATCH_LOCK_KEY)
        raise

    # delay() 成功后不释放锁，让 TTL 自然过期
    batch_quality_review_task.delay(result_ids, batch_id)

    return {
        "batch_id": batch_id,
        "total_count": len(result_ids),
        "message": f"已提交 {len(result_ids)} 条未审查高中风险结果进行二次审查"
    }


def _apply_review_filters(stmt, count_stmt, result_id, review_status, batch_id,
                           secondary_risk_level, risk_type, priority, confirmed):
    """为审查结果查询的主查询和 count 查询同时应用所有过滤条件"""
    if result_id:
        stmt = stmt.where(QualityReviewResult.result_id == result_id)
        count_stmt = count_stmt.where(QualityReviewResult.result_id == result_id)
    if review_status:
        stmt = stmt.where(QualityReviewResult.review_status == review_status)
        count_stmt = count_stmt.where(QualityReviewResult.review_status == review_status)
    if batch_id:
        stmt = stmt.where(QualityReviewResult.batch_id == batch_id)
        count_stmt = count_stmt.where(QualityReviewResult.batch_id == batch_id)
    if secondary_risk_level:
        levels = [l.strip() for l in secondary_risk_level.split(',') if l.strip()]
        if levels:
            col = QualityReviewResult.secondary_risk_level
            condition = col == levels[0] if len(levels) == 1 else col.in_(levels)
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
    if risk_type:
        types = [t.strip() for t in risk_type.split(',') if t.strip()]
        if types:
            col = QualityReviewResult.risk_type
            condition = col == types[0] if len(types) == 1 else col.in_(types)
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
    if priority:
        priorities = [p.strip() for p in priority.split(',') if p.strip()]
        if priorities:
            col = QualityReviewResult.priority
            condition = col == priorities[0] if len(priorities) == 1 else col.in_(priorities)
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
    if confirmed is not None:
        stmt = stmt.where(QualityReviewResult.confirmed == confirmed)
        count_stmt = count_stmt.where(QualityReviewResult.confirmed == confirmed)
    return stmt, count_stmt


class BatchReviewRequest(BaseModel):
    result_ids: list[int]


@router.post("/quality-review/batch")
async def batch_quality_review(
    request: BatchReviewRequest,
    current_user: dict = Depends(require_permission("write:quality_review")),
):
    """手动批量二次审查（用户指定 ID 列表）

    流程：
    1. 验证结果数量（最多100条）
    2. 验证所有结果符合条件（高中风险、未审查）
    3. 生成批次号（UUID）
    4. 提交Celery任务
    5. 返回批次号和任务总数
    """
    if len(request.result_ids) > 100:
        raise HTTPException(status_code=400, detail="批量审查最多100条")
    if len(request.result_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一条质检结果")

    # 分布式锁防并发
    redis_client = get_redis()
    if redis_client:
        acquired = redis_client.set(_AUTO_BATCH_LOCK_KEY, "1", nx=True, ex=_AUTO_BATCH_LOCK_TTL)
        if not acquired:
            raise HTTPException(status_code=409, detail="已有审查任务正在执行，请稍后重试")

    try:
        async with async_session() as session:
            stmt = select(QualityCheckResult).where(
                QualityCheckResult.id.in_(request.result_ids)
            )
            result = await session.execute(stmt)
            quality_results = result.scalars().all()

            if len(quality_results) != len(request.result_ids):
                raise HTTPException(status_code=400, detail="部分质检结果不存在")

            invalid_ids = []
            already_reviewed_ids = []
            for qr in quality_results:
                if qr.has_secondary_review:
                    already_reviewed_ids.append(qr.id)
                else:
                    effective_risk = qr.modified_risk_level or qr.risk_level
                    if effective_risk not in ["high", "medium"]:
                        invalid_ids.append(qr.id)

            if invalid_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"结果ID {invalid_ids} 不符合高中风险条件"
                )
            if already_reviewed_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"结果ID {already_reviewed_ids} 已完成二次审查"
                )

        batch_id = str(uuid.uuid4())
        batch_quality_review_task.delay(request.result_ids, batch_id)

        return {
            "batch_id": batch_id,
            "total_count": len(request.result_ids),
            "message": f"已提交 {len(request.result_ids)} 条二次审查任务"
        }
    except HTTPException:
        raise
    except Exception:
        if redis_client:
            redis_client.delete(_AUTO_BATCH_LOCK_KEY)
        raise


@router.post("/quality-review/instant/{result_id}")
async def instant_quality_review(
    result_id: int,
    current_user: dict = Depends(require_permission("write:quality_review")),
):
    """单条即时二次审查

    流程：
    1. 验证质检结果存在且符合条件（高中风险、未审查）
    2. 查询质检结果详情（聊天记录、关键证据）
    3. 同步调用二次审查Agent
    4. 保存结果到数据库
    5. 更新质检结果标记
    6. 返回审查结果
    """
    async with async_session() as session:
        # 1. 查询质检结果
        stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
        result = await session.execute(stmt)
        quality_result = result.scalar_one_or_none()

        if not quality_result:
            raise HTTPException(status_code=404, detail="质检结果不存在")

        # 2. 验证条件
        effective_risk_level = quality_result.modified_risk_level or quality_result.risk_level
        if effective_risk_level not in ["high", "medium"]:
            raise HTTPException(status_code=400, detail="仅支持高中风险结果的二次审查")

        if quality_result.has_secondary_review:
            raise HTTPException(status_code=400, detail="该结果已完成二次审查")

        # 3. 查询详情（关键证据）
        detail_stmt = select(QualityCheckDetail).where(QualityCheckDetail.result_id == result_id)
        detail_result = await session.execute(detail_stmt)
        detail = detail_result.scalar_one_or_none()

        key_evidence = detail.key_evidence if detail else []

        # 4. 获取聊天记录（从任务表获取 end_time）
        task_end_time = "2099-12-31 23:59:59"
        if quality_result.task_id:
            task_stmt = select(QualityCheckTask).where(QualityCheckTask.id == quality_result.task_id)
            task_result = await session.execute(task_stmt)
            task = task_result.scalar_one_or_none()
            if task and task.end_time:
                task_end_time = task.end_time

        chat_records = get_chat_records_for_quality_check(
            user_id=quality_result.user_id,
            friend_id=quality_result.friend_id,
            end_time=task_end_time,
        )

        # 5. 同步调用二次审查Agent（放入线程池，避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        review_result = await loop.run_in_executor(
            None,
            lambda: quality_review_agent(
                result_id=result_id,
                chat_records=chat_records,
                key_evidence=key_evidence,
                issue_summary=quality_result.issue_summary or "",
                initial_risk_level=effective_risk_level,
                raw_response=detail.raw_response if detail else "",
            )
        )

        # 6. 保存审查结果
        review_record = QualityReviewResult(
            result_id=result_id,
            confirmed=review_result.get("confirmed"),
            risk_type=review_result.get("risk_type"),
            priority=review_result.get("priority"),
            first_mention_time=review_result.get("first_mention_time"),
            secondary_risk_level=review_result.get("secondary_risk_level"),
            review_reason=review_result.get("review_reason"),
            suggested_action=review_result.get("suggested_action"),
            confidence=review_result.get("confidence"),
            review_status="completed" if review_result.get("status") == "success" else "failed",
            review_mode="instant",
            error_msg=review_result.get("error_msg"),
            created_at=to_naive_shanghai(now_shanghai()),
            completed_at=to_naive_shanghai(now_shanghai()) if review_result.get("status") == "success" else None,
        )
        session.add(review_record)

        # 7. 更新质检结果标记
        quality_result.has_secondary_review = True

        await session.commit()
        await session.refresh(review_record)

        return review_record.to_dict()


@router.get("/quality-review")
async def query_quality_review_results(
    result_id: int | None = Query(None, description="关联质检结果ID"),
    review_status: str | None = Query(None, description="审查状态：pending/completed/failed"),
    batch_id: str | None = Query(None, description="批次号"),
    secondary_risk_level: str | None = Query(None, description="二次风险等级"),
    risk_type: str | None = Query(None, description="风险类型：退费/投诉/其他"),
    priority: str | None = Query(None, description="优先级：P0/P1/P2/P3"),
    confirmed: bool | None = Query(None, description="是否确认涉及退费或投诉"),
    sort_field: str | None = Query(None, description="排序字段：completed_at, priority"),
    sort_order: str | None = Query("desc", description="排序方向：asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("read:quality_review")),
):
    """查询二次审查结果列表（含关联质检结果信息）"""
    async with async_session() as session:
        # 使用JOIN查询，关联质检结果表
        stmt = (
            select(
                QualityReviewResult,
                QualityCheckResult.user_name,
                QualityCheckResult.friend_name,
                QualityCheckResult.risk_level.label("original_risk_level"),
                QualityCheckResult.modified_risk_level,
                QualityCheckResult.risk_category,
                QualityCheckResult.issue_summary,
                QualityCheckResult.process_status,
                QualityCheckResult.remark,
            )
            .outerjoin(QualityCheckResult, QualityReviewResult.result_id == QualityCheckResult.id)
        )

        # 总数统计
        count_stmt = select(func.count()).select_from(QualityReviewResult)

        # 应用所有过滤条件
        stmt, count_stmt = _apply_review_filters(
            stmt, count_stmt, result_id, review_status, batch_id,
            secondary_risk_level, risk_type, priority, confirmed
        )

        total = await session.scalar(count_stmt)

        # 排序
        sort_column_map = {
            "completed_at": QualityReviewResult.completed_at,
            "priority": QualityReviewResult.priority,
            "created_at": QualityReviewResult.created_at,
        }
        order_by_clause = QualityReviewResult.created_at.desc()
        if sort_field and sort_field in sort_column_map:
            col = sort_column_map[sort_field]
            order_by_clause = col.asc() if sort_order == "asc" else col.desc()
        stmt = stmt.order_by(order_by_clause)

        # 分页查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.all()

        # 组装返回数据
        data = []
        for row in rows:
            review = row[0]
            item = review.to_dict()
            item["user_name"] = row[1]
            item["friend_name"] = row[2]
            item["original_risk_level"] = row[3]
            item["modified_risk_level"] = row[4]
            item["risk_category"] = row[5]
            item["issue_summary"] = row[6]
            item["process_status"] = row[7]
            item["remark"] = row[8]
            data.append(item)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": data,
        }


@router.get("/quality-review/{review_id}")
async def get_quality_review_detail(
    review_id: int,
    current_user: dict = Depends(require_permission("read:quality_review")),
):
    """获取单条二次审查详情，包含关联的质检结果信息"""
    async with async_session() as session:
        # 查询审查结果
        stmt = select(QualityReviewResult).where(QualityReviewResult.id == review_id)
        result = await session.execute(stmt)
        review_record = result.scalar_one_or_none()

        if not review_record:
            raise HTTPException(status_code=404, detail="审查记录不存在")

        # 查询关联的质检结果
        quality_stmt = select(QualityCheckResult).where(
            QualityCheckResult.id == review_record.result_id
        )
        quality_result = await session.execute(quality_stmt)
        quality_record = quality_result.scalar_one_or_none()

        # 合并返回
        data = review_record.to_dict()
        if quality_record:
            data["original_risk_level"] = quality_record.modified_risk_level or quality_record.risk_level
            data["quality_check_result"] = {
                "risk_level": quality_record.risk_level,
                "modified_risk_level": quality_record.modified_risk_level,
                "issue_summary": quality_record.issue_summary,
                "user_id": quality_record.user_id,
                "user_name": quality_record.user_name,
                "friend_id": quality_record.friend_id,
                "friend_name": quality_record.friend_name,
                "chat_title": quality_record.chat_title,
                "phone": quality_record.phone,
                "detected_keywords": quality_record.detected_keywords,
                "risk_category": quality_record.risk_category,
                "trigger_party": quality_record.trigger_party,
                "action_priority": quality_record.action_priority,
                "recommended_owner": quality_record.recommended_owner,
                "action_type": quality_record.action_type,
                "follow_up_deadline": quality_record.follow_up_deadline,
                "needs_manual_review": quality_record.needs_manual_review,
                "process_status": quality_record.process_status,
                "created_at": quality_record.created_at.isoformat() if quality_record.created_at else None,
            }

            # 查询 detail 表获取 key_evidence
            detail_stmt = select(QualityCheckDetail).where(
                QualityCheckDetail.result_id == quality_record.id
            )
            detail_result = await session.execute(detail_stmt)
            detail = detail_result.scalar_one_or_none()
            if detail:
                data["quality_check_result"]["key_evidence"] = detail.key_evidence or []

        return data


class ReviewUpdateRequest(BaseModel):
    confirmed: bool | None = None
    risk_type: str | None = None
    priority: str | None = None
    first_mention_time: str | None = None
    secondary_risk_level: str | None = None
    review_reason: str | None = None
    suggested_action: str | None = None


@router.put("/quality-review/{review_id}")
async def update_quality_review(
    review_id: int,
    request: ReviewUpdateRequest,
    current_user: dict = Depends(require_permission("write:quality_review")),
):
    """编辑二次审查结果"""
    async with async_session() as session:
        stmt = select(QualityReviewResult).where(QualityReviewResult.id == review_id)
        result = await session.execute(stmt)
        review_record = result.scalar_one_or_none()

        if not review_record:
            raise HTTPException(status_code=404, detail="审查记录不存在")

        # 更新传入的字段
        if request.confirmed is not None:
            review_record.confirmed = request.confirmed
        if request.risk_type is not None:
            review_record.risk_type = request.risk_type
        if request.priority is not None:
            review_record.priority = request.priority
        if request.first_mention_time is not None:
            review_record.first_mention_time = request.first_mention_time
        if request.secondary_risk_level is not None:
            review_record.secondary_risk_level = request.secondary_risk_level
        if request.review_reason is not None:
            review_record.review_reason = request.review_reason
        if request.suggested_action is not None:
            review_record.suggested_action = request.suggested_action

        await session.commit()
        await session.refresh(review_record)

        return review_record.to_dict()
