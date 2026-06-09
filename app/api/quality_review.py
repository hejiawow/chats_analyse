# -*- coding: utf-8 -*-
"""质检二次审查 API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_

from app.models.database import async_session
from app.models.result import QualityCheckResult, QualityReviewResult, QualityCheckDetail
from app.services.dependencies import require_permission
from app.tasks.quality_review import batch_quality_review_task

router = APIRouter()


@router.post("/quality-review/auto-batch")
async def auto_batch_quality_review(
    current_user: dict = Depends(require_permission("write:quality_review")),
):
    """一键审查所有未审查的高中风险结果

    流程：
    1. 查询所有 has_secondary_review=False 且有效风险等级为 high/medium 的结果
    2. 生成批次号（UUID）
    3. 提交Celery异步任务
    4. 返回批次号和总数
    """
    async with async_session() as session:
        # 查询所有符合条件的未审查结果ID
        # 有效风险等级：modified_risk_level 优先，无修正时用 risk_level
        # 使用 or_ 处理 has_secondary_review 为 NULL 的旧数据
        # 子查询排除已存在 completed 审查记录的 result_id
        completed_subq = (
            select(QualityReviewResult.result_id)
            .where(QualityReviewResult.review_status == "completed")
            .scalar_subquery()
        )
        stmt = select(QualityCheckResult.id).where(
            or_(
                QualityCheckResult.has_secondary_review == False,
                QualityCheckResult.has_secondary_review == None,
            ),
            QualityCheckResult.id.not_in(completed_subq),
            or_(
                QualityCheckResult.modified_risk_level.in_(["high", "medium"]),
                and_(
                    QualityCheckResult.modified_risk_level == None,
                    QualityCheckResult.risk_level.in_(["high", "medium"])
                )
            )
        )
        result = await session.execute(stmt)
        result_ids = [row[0] for row in result.all()]

    if not result_ids:
        raise HTTPException(status_code=404, detail="暂无未审查的高中风险结果")

    batch_id = str(uuid.uuid4())
    batch_quality_review_task.delay(result_ids, batch_id)

    return {
        "batch_id": batch_id,
        "total_count": len(result_ids),
        "message": f"已提交 {len(result_ids)} 条未审查高中风险结果进行二次审查"
    }



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
                QualityCheckResult.risk_category,
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
            item["risk_category"] = row[5]
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