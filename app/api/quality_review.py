# -*- coding: utf-8 -*-
"""质检二次审查 API"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from app.models.database import async_session
from app.models.result import QualityCheckResult, QualityReviewResult, QualityCheckDetail, QualityCheckTask
from app.services.dependencies import require_permission
from app.agents.quality_review import quality_review_agent
from app.services.hujing_api import get_chat_records_for_quality_check
from app.tasks.quality_review import batch_quality_review_task
from config import now_shanghai, to_naive_shanghai

router = APIRouter()


class BatchReviewRequest(BaseModel):
    result_ids: list[int]


@router.post("/quality-review/batch")
async def batch_quality_review(
    request: BatchReviewRequest,
    current_user: dict = Depends(require_permission("write:quality_review")),
):
    """批量异步二次审查

    流程：
    1. 验证结果数量（最多100条）
    2. 验证所有结果符合条件（高中风险）
    3. 生成批次号（UUID）
    4. 提交Celery任务
    5. 返回批次号和任务总数
    """
    # 1. 验证数量
    if len(request.result_ids) > 100:
        raise HTTPException(status_code=400, detail="批量审查最多100条")

    if len(request.result_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一条质检结果")

    # 2. 验证结果符合条件
    async with async_session() as session:
        stmt = select(QualityCheckResult).where(
            QualityCheckResult.id.in_(request.result_ids)
        )
        result = await session.execute(stmt)
        quality_results = result.scalars().all()

        # 检查数量匹配
        if len(quality_results) != len(request.result_ids):
            raise HTTPException(status_code=400, detail="部分质检结果不存在")

        # 检查风险等级
        invalid_ids = []
        already_reviewed_ids = []
        for qr in quality_results:
            effective_risk = qr.modified_risk_level or qr.risk_level
            if effective_risk not in ["high", "medium"]:
                invalid_ids.append(qr.id)
            if qr.has_secondary_review:
                already_reviewed_ids.append(qr.id)

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

    # 3. 生成批次号
    batch_id = str(uuid.uuid4())

    # 4. 提交Celery任务
    batch_quality_review_task.delay(request.result_ids, batch_id)

    # 5. 返回结果
    return {
        "batch_id": batch_id,
        "total_count": len(request.result_ids),
        "message": f"已提交 {len(request.result_ids)} 条二次审查任务"
    }


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

        # 4. 获取聊天记录（使用相同的查询函数）
        # 从任务表获取end_time，如果没有则使用默认值
        task_end_time = "2099-12-31 23:59:59"  # 默认值
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

        # 5. 同步调用二次审查Agent
        review_result = quality_review_agent(
            result_id=result_id,
            chat_records=chat_records,
            key_evidence=key_evidence,
            issue_summary=quality_result.issue_summary or "",
            initial_risk_level=effective_risk_level,
            raw_response=detail.raw_response if detail else "",
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

        # 刷新以获取ID
        await session.refresh(review_record)

        # 8. 返回结果
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
            )
            .outerjoin(QualityCheckResult, QualityReviewResult.result_id == QualityCheckResult.id)
        )

        if result_id:
            stmt = stmt.where(QualityReviewResult.result_id == result_id)
        if review_status:
            stmt = stmt.where(QualityReviewResult.review_status == review_status)
        if batch_id:
            stmt = stmt.where(QualityReviewResult.batch_id == batch_id)
        if secondary_risk_level:
            stmt = stmt.where(QualityReviewResult.secondary_risk_level == secondary_risk_level)
        if risk_type:
            stmt = stmt.where(QualityReviewResult.risk_type == risk_type)
        if priority:
            stmt = stmt.where(QualityReviewResult.priority == priority)
        if confirmed is not None:
            stmt = stmt.where(QualityReviewResult.confirmed == confirmed)

        # 总数统计
        count_stmt = select(func.count()).select_from(QualityReviewResult)
        if result_id:
            count_stmt = count_stmt.where(QualityReviewResult.result_id == result_id)
        if review_status:
            count_stmt = count_stmt.where(QualityReviewResult.review_status == review_status)
        if batch_id:
            count_stmt = count_stmt.where(QualityReviewResult.batch_id == batch_id)
        if secondary_risk_level:
            count_stmt = count_stmt.where(QualityReviewResult.secondary_risk_level == secondary_risk_level)
        if risk_type:
            count_stmt = count_stmt.where(QualityReviewResult.risk_type == risk_type)
        if priority:
            count_stmt = count_stmt.where(QualityReviewResult.priority == priority)
        if confirmed is not None:
            count_stmt = count_stmt.where(QualityReviewResult.confirmed == confirmed)

        total = await session.scalar(count_stmt)

        # 分页查询
        stmt = stmt.order_by(QualityReviewResult.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.all()

        # 组装返回数据
        data = []
        for row in rows:
            review = row[0]  # QualityReviewResult
            item = review.to_dict()
            item["user_name"] = row[1]
            item["friend_name"] = row[2]
            item["original_risk_level"] = row[3]
            item["modified_risk_level"] = row[4]
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
                "user_name": quality_record.user_name,
                "friend_name": quality_record.friend_name,
                "detected_keywords": quality_record.detected_keywords,
                "risk_category": quality_record.risk_category,
                "trigger_party": quality_record.trigger_party,
                "process_status": quality_record.process_status,
                "created_at": quality_record.created_at.isoformat() if quality_record.created_at else None,
            }

        return data