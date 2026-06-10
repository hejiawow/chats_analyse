# -*- coding: utf-8 -*-
"""质检检测结果查询 API"""
import io
import csv
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.models.database import async_session
from app.models.result import QualityCheckResult, QualityCheckModificationLog, QualityCheckDetail, QualityCheckTask
from app.services.dependencies import require_permission, get_current_user
from app.services.cache import cache_get, cache_set, cache_delete, cache_clear_pattern
from app.services.hujing_api import get_chat_records, get_chat_records_for_quality_check
from config import now_shanghai, to_naive_shanghai, settings

_STATS_CACHE_TTL = 300  # 统计缓存：5 分钟
_STATS_CACHE_KEY = "quality_check:stats"

router = APIRouter()


def _build_time_filter(start_time: str | None, end_time: str | None):
    """构建检测时间范围筛选条件（直接通过任务表的时间字段筛选）

    筛选逻辑：检测时间范围与筛选时间范围有交集。
    - task.end_time >= filter_start（任务检测结束时间在筛选开始时间之后）
    - task.start_time <= filter_end（任务检测起始时间在筛选结束时间之前）
    """
    conditions = []
    if start_time:
        conditions.append(QualityCheckTask.end_time >= start_time)
    if end_time:
        conditions.append(QualityCheckTask.start_time <= end_time)
    return and_(*conditions) if conditions else None


def _apply_task_join(stmt):
    """给查询语句添加 LEFT JOIN quality_check_tasks（用于时间筛选）"""
    return stmt.outerjoin(
        QualityCheckTask, QualityCheckResult.task_id == QualityCheckTask.id
    )


def escape_like_pattern(pattern: str) -> str:
    """Escape special LIKE wildcards (% _, backslash)."""
    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_risk_keyword_filter(stmt, risk_levels: List[str] | None, keywords: List[str] | None):
    """Build risk level and keyword filter conditions

    风险等级筛选逻辑：使用"有效风险等级" = COALESCE(modified_risk_level, risk_level)
    即优先使用人工修正后的等级，若无修正则使用原始等级
    """
    if risk_levels:
        # 使用 COALESCE 函数：modified_risk_level 优先，否则使用 risk_level
        effective_risk_level = func.coalesce(
            QualityCheckResult.modified_risk_level,
            QualityCheckResult.risk_level
        )
        stmt = stmt.where(effective_risk_level.in_(risk_levels))
    if keywords:
        keyword_conditions = [
            QualityCheckResult.detected_keywords.ilike(f"%{escape_like_pattern(kw)}%", escape="\\")
            for kw in keywords
        ]
        stmt = stmt.where(or_(*keyword_conditions))
    return stmt


def _apply_processing_filters(
    stmt,
    action_priorities: List[str] | None = None,
    risk_categories: List[str] | None = None,
    recommended_owner: str | None = None,
    action_type: str | None = None,
    needs_manual_review: bool | None = None,
    process_status: str | None = None,
):
    """应用质检处理建议相关筛选。"""
    if action_priorities:
        stmt = stmt.where(QualityCheckResult.action_priority.in_(action_priorities))
    if risk_categories:
        stmt = stmt.where(QualityCheckResult.risk_category.in_(risk_categories))
    if recommended_owner:
        stmt = stmt.where(QualityCheckResult.recommended_owner == recommended_owner)
    if action_type:
        stmt = stmt.where(QualityCheckResult.action_type == action_type)
    if needs_manual_review is not None:
        stmt = stmt.where(QualityCheckResult.needs_manual_review == needs_manual_review)
    if process_status:
        stmt = stmt.where(QualityCheckResult.process_status == process_status)
    return stmt


@router.get("/quality-check")
async def query_quality_check_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    risk_levels: List[str] = Query(None, alias="risk_levels[]", description="风险等级列表：high/medium/low/none"),
    keywords: List[str] = Query(None, alias="keywords[]", description="关键词列表"),
#     risk_level: str | None = Query(None, description="风险等级：high/medium/low/none"),
    trigger_party: str | None = Query(None, description="触发方：sales/customer/both"),
#     keyword: str | None = Query(None, description="关键词内容（模糊匹配）"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    task_id: int | None = Query(None, description="关联质检任务ID"),
    action_priority: str | None = Query(None, description="处理优先级（单选，向后兼容）"),
    action_priorities: List[str] = Query(None, alias="action_priorities[]", description="处理优先级列表：P0/P1/P2/P3"),
    risk_categories: List[str] = Query(None, alias="risk_categories[]", description="风险类别列表"),
    recommended_owner: str | None = Query(None, description="建议责任方"),
    action_type: str | None = Query(None, description="建议动作类型"),
    needs_manual_review: bool | None = Query(None, description="是否需要人工复核"),
    process_status: str | None = Query(None, description="处理状态"),
    sort_field: str | None = Query(None, description="排序字段：created_at/action_priority/risk_level"),
    sort_order: str | None = Query(None, description="排序方向：ascend/descend"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """查询质检检测结果，支持筛选。

    时间筛选：通过关联任务表的 start_time/end_time 筛选，
    筛选逻辑为检测时间范围与筛选时间范围有交集。
    """
    # 合并向后兼容的单选 action_priority 到列表
    effective_priorities = action_priorities
    if not effective_priorities and action_priority:
        effective_priorities = [action_priority]

    async with async_session() as session:
        stmt = select(QualityCheckResult)
        # LEFT JOIN 任务表，用于时间筛选和获取任务时间范围
        stmt = _apply_task_join(stmt)

        if user_id:
            stmt = stmt.where(QualityCheckResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(QualityCheckResult.friend_id == friend_id)
        stmt = _build_risk_keyword_filter(stmt, risk_levels, keywords)
        stmt = _apply_processing_filters(stmt, effective_priorities, risk_categories, recommended_owner, action_type, needs_manual_review, process_status)
        if trigger_party:
            stmt = stmt.where(QualityCheckResult.trigger_party == trigger_party)

        # 按任务ID筛选
        if task_id is not None:
            stmt = stmt.where(QualityCheckResult.task_id == task_id)

        # 按检测时间范围筛选（通过任务表）
        time_filter = _build_time_filter(start_time, end_time)
        if time_filter is not None:
            stmt = stmt.where(time_filter)

        # 动态排序
        if sort_field == "action_priority":
            priority_order = case(
                (QualityCheckResult.action_priority == "P0", 1),
                (QualityCheckResult.action_priority == "P1", 2),
                (QualityCheckResult.action_priority == "P2", 3),
                (QualityCheckResult.action_priority == "P3", 4),
                else_=5,
            )
            stmt = stmt.order_by(priority_order.asc() if sort_order == "ascend" else priority_order.desc())
        elif sort_field == "risk_level":
            effective_risk = func.coalesce(
                QualityCheckResult.modified_risk_level,
                QualityCheckResult.risk_level
            )
            risk_order = case(
                (effective_risk == "high", 1),
                (effective_risk == "medium", 2),
                (effective_risk == "low", 3),
                (effective_risk == "none", 4),
                else_=5,
            )
            stmt = stmt.order_by(risk_order.asc() if sort_order == "ascend" else risk_order.desc())
        elif sort_field == "created_at" and sort_order == "ascend":
            stmt = stmt.order_by(QualityCheckResult.created_at.asc())
        else:
            stmt = stmt.order_by(QualityCheckResult.created_at.desc())

        # 总数（需同样的 JOIN）
        count_stmt = select(func.count()).select_from(
            QualityCheckResult
        ).outerjoin(
            QualityCheckTask, QualityCheckResult.task_id == QualityCheckTask.id
        )
        if user_id:
            count_stmt = count_stmt.where(QualityCheckResult.user_id == user_id)
        if friend_id is not None:
            count_stmt = count_stmt.where(QualityCheckResult.friend_id == friend_id)
        count_stmt = _build_risk_keyword_filter(count_stmt, risk_levels, keywords)
        count_stmt = _apply_processing_filters(count_stmt, effective_priorities, risk_categories, recommended_owner, action_type, needs_manual_review, process_status)
        if trigger_party:
            count_stmt = count_stmt.where(QualityCheckResult.trigger_party == trigger_party)
        if task_id is not None:
            count_stmt = count_stmt.where(QualityCheckResult.task_id == task_id)
        if time_filter is not None:
            count_stmt = count_stmt.where(time_filter)

        total = await session.scalar(count_stmt)

        # 分页数据
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()

        # 批量获取关联任务的时间范围，填充到返回数据中
        task_ids = {r.task_id for r in records if r.task_id}
        task_map = {}
        if task_ids:
            task_stmt = select(QualityCheckTask).where(QualityCheckTask.id.in_(task_ids))
            task_result = await session.execute(task_stmt)
            task_map = {t.id: t for t in task_result.scalars().all()}

        data = []
        for r in records:
            item = r.to_dict()
            # 从任务表获取检测时间范围
            task = task_map.get(r.task_id)
            if task:
                item["check_time_start"] = task.start_time
                item["check_time_end"] = task.end_time
            data.append(item)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": data,
        }


@router.get("/quality-check/stats")
async def get_quality_check_stats(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    trigger_party: str | None = Query(None, description="触发方：sales/customer/both"),
    keyword: str | None = Query(None, description="关键词"),
    keywords: List[str] = Query(None, alias="keywords[]", description="关键词列表"),
    action_priority: str | None = Query(None, description="处理优先级（单选，向后兼容）"),
    action_priorities: List[str] = Query(None, alias="action_priorities[]", description="处理优先级列表：P0/P1/P2/P3"),
    risk_categories: List[str] = Query(None, alias="risk_categories[]", description="风险类别列表"),
    recommended_owner: str | None = Query(None, description="建议责任方"),
    action_type: str | None = Query(None, description="建议动作类型"),
    needs_manual_review: bool | None = Query(None, description="是否需要人工复核"),
    process_status: str | None = Query(None, description="处理状态"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """获取质检结果统计：总数、风险分布、关键词频次（支持筛选）

    时间筛选：通过任务表检测时间范围筛选，兼容旧数据
    注意：风险等级筛选不影响统计，只影响表格
    """
    # 合并向后兼容的单选 action_priority 到列表
    effective_priorities = action_priorities
    if not effective_priorities and action_priority:
        effective_priorities = [action_priority]

    # 筛选条件
    user_id_filter = user_id if user_id else None
    keyword_values = list(keywords or [])
    if keyword:
        keyword_values.append(keyword)

    # 判断是否有筛选条件（影响缓存策略）
    has_filters = (
        user_id_filter or friend_id or trigger_party or keyword_values
        or effective_priorities or risk_categories or recommended_owner or action_type
        or needs_manual_review is not None or process_status
        or start_time or end_time
    )

    # 缓存策略：无筛选条件时使用缓存，有筛选条件时不缓存
    cache_key = _STATS_CACHE_KEY
    if user_id_filter:
        cache_key = f"{_STATS_CACHE_KEY}:user:{user_id_filter}"

    # 只有无任何筛选条件时才使用缓存
    if not has_filters:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    # 构建检测时间范围筛选条件（通过任务表）
    time_filter = _build_time_filter(start_time, end_time)

    async with async_session() as session:
        # 总数统计（需 JOIN 任务表用于时间筛选）
        count_stmt = select(func.count()).select_from(
            QualityCheckResult
        ).outerjoin(
            QualityCheckTask, QualityCheckResult.task_id == QualityCheckTask.id
        )
        if user_id_filter:
            count_stmt = count_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            count_stmt = count_stmt.where(QualityCheckResult.friend_id == friend_id)
        if trigger_party:
            count_stmt = count_stmt.where(QualityCheckResult.trigger_party == trigger_party)
        count_stmt = _build_risk_keyword_filter(count_stmt, None, keyword_values)
        count_stmt = _apply_processing_filters(
            count_stmt,
            effective_priorities,
            risk_categories,
            recommended_owner,
            action_type,
            needs_manual_review,
            process_status,
        )
        if time_filter is not None:
            count_stmt = count_stmt.where(time_filter)
        total = await session.scalar(count_stmt)

        # 风险等级分布（使用有效风险等级 = COALESCE(modified_risk_level, risk_level))
        effective_risk_level = func.coalesce(
            QualityCheckResult.modified_risk_level,
            QualityCheckResult.risk_level
        )
        risk_stmt = select(
            effective_risk_level.label("risk_level"),
            func.count().label("count")
        ).select_from(
            QualityCheckResult
        ).outerjoin(
            QualityCheckTask, QualityCheckResult.task_id == QualityCheckTask.id
#         ).group_by(QualityCheckResult.risk_level)
        ).group_by(effective_risk_level)
        if user_id_filter:
            risk_stmt = risk_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            risk_stmt = risk_stmt.where(QualityCheckResult.friend_id == friend_id)
        if trigger_party:
            risk_stmt = risk_stmt.where(QualityCheckResult.trigger_party == trigger_party)
        risk_stmt = _build_risk_keyword_filter(risk_stmt, None, keyword_values)
        risk_stmt = _apply_processing_filters(
            risk_stmt,
            effective_priorities,
            risk_categories,
            recommended_owner,
            action_type,
            needs_manual_review,
            process_status,
        )
        if time_filter is not None:
            risk_stmt = risk_stmt.where(time_filter)
        risk_result = await session.execute(risk_stmt)
        risk_distribution = {row.risk_level or "none": row.count for row in risk_result}

        # 优先级分布统计
        priority_stmt = select(
            QualityCheckResult.action_priority.label("priority"),
            func.count().label("count")
        ).select_from(
            QualityCheckResult
        ).outerjoin(
            QualityCheckTask, QualityCheckResult.task_id == QualityCheckTask.id
        ).group_by(QualityCheckResult.action_priority)
        if user_id_filter:
            priority_stmt = priority_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            priority_stmt = priority_stmt.where(QualityCheckResult.friend_id == friend_id)
        if trigger_party:
            priority_stmt = priority_stmt.where(QualityCheckResult.trigger_party == trigger_party)
        priority_stmt = _build_risk_keyword_filter(priority_stmt, None, keyword_values)
        priority_stmt = _apply_processing_filters(
            priority_stmt,
            effective_priorities,
            risk_categories,
            recommended_owner,
            action_type,
            needs_manual_review,
            process_status,
        )
        if time_filter is not None:
            priority_stmt = priority_stmt.where(time_filter)
        priority_result = await session.execute(priority_stmt)
        priority_distribution = {row.priority or "unknown": row.count for row in priority_result}

        # 关键词频次统计
        keyword_stmt = select(QualityCheckResult.detected_keywords).select_from(
            QualityCheckResult
        ).outerjoin(
            QualityCheckTask, QualityCheckResult.task_id == QualityCheckTask.id
        )
        if user_id_filter:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.friend_id == friend_id)
        if trigger_party:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.trigger_party == trigger_party)
        keyword_stmt = _build_risk_keyword_filter(keyword_stmt, None, keyword_values)
        keyword_stmt = _apply_processing_filters(
            keyword_stmt,
            effective_priorities,
            risk_categories,
            recommended_owner,
            action_type,
            needs_manual_review,
            process_status,
        )
        if time_filter is not None:
            keyword_stmt = keyword_stmt.where(time_filter)
        keyword_result = await session.execute(keyword_stmt)

        keyword_counts = {}
        for row in keyword_result:
            if row.detected_keywords:
                for kw in row.detected_keywords.split(","):
                    kw = kw.strip()
                    if kw:
                        keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        keyword_frequency = sorted(
            [{"keyword": k, "count": c} for k, c in keyword_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]

        result = {
            "total": total,
            "risk_distribution": risk_distribution,
            "priority_distribution": priority_distribution,
            "keyword_frequency": keyword_frequency,
        }

        # 只有无筛选条件时才存入缓存
        if not has_filters:
            cache_set(cache_key, result, _STATS_CACHE_TTL)

        return result


@router.get("/quality-check/export")
async def export_quality_check_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    risk_levels: List[str] = Query(None, alias="risk_levels[]", description="风险等级列表"),
    keywords: List[str] = Query(None, alias="keywords[]", description="关键词列表"),
    trigger_party: str | None = Query(None, description="触发方：sales/customer/both"),
    action_priority: str | None = Query(None, description="处理优先级（单选，向后兼容）"),
    action_priorities: List[str] = Query(None, alias="action_priorities[]", description="处理优先级列表：P0/P1/P2/P3"),
    risk_categories: List[str] = Query(None, alias="risk_categories[]", description="风险类别列表"),
    recommended_owner: str | None = Query(None, description="建议责任方"),
    action_type: str | None = Query(None, description="建议动作类型"),
    needs_manual_review: bool | None = Query(None, description="是否需要人工复核"),
    process_status: str | None = Query(None, description="处理状态"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    limit: int = Query(10000, ge=1, le=50000, description="导出数量上限"),
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """导出质检结果为 CSV 文件（带数量限制）

    时间筛选：通过任务表检测时间范围筛选，兼容旧数据
    """
    # 合并向后兼容的单选 action_priority 到列表
    effective_priorities = action_priorities
    if not effective_priorities and action_priority:
        effective_priorities = [action_priority]

    # 构建检测时间范围筛选条件（通过任务表）
    time_filter = _build_time_filter(start_time, end_time)

    async with async_session() as session:
        stmt = select(QualityCheckResult)
        # LEFT JOIN 任务表，用于时间筛选和获取任务时间范围
        stmt = _apply_task_join(stmt)
        if user_id:
            stmt = stmt.where(QualityCheckResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(QualityCheckResult.friend_id == friend_id)
        stmt = _build_risk_keyword_filter(stmt, risk_levels, keywords)
        stmt = _apply_processing_filters(stmt, effective_priorities, risk_categories, recommended_owner, action_type, needs_manual_review, process_status)
        if trigger_party:
            stmt = stmt.where(QualityCheckResult.trigger_party == trigger_party)
        if time_filter is not None:
            stmt = stmt.where(time_filter)
        stmt = stmt.order_by(QualityCheckResult.created_at.desc())
        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        records = result.scalars().all()

        # 批量获取关联任务的时间范围
        task_ids = {r.task_id for r in records if r.task_id}
        task_map = {}
        if task_ids:
            task_stmt = select(QualityCheckTask).where(QualityCheckTask.id.in_(task_ids))
            task_result = await session.execute(task_stmt)
            task_map = {t.id: t for t in task_result.scalars().all()}

    # 构建 CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # 表头
    writer.writerow([
        "ID", "销售ID", "好友ID", "好友姓名", "好友备注", "好友别名", "绑定手机号", "备注手机号",
        "检测时间范围", "聊天记录数",
        "关键词检测", "检测关键词", "风险等级", "触发方", "风险类别",
        "问题摘要", "处理优先级", "建议责任方", "建议动作类型", "处理时限",
        "需人工复核", "AI置信度", "处理状态", "创建时间"
    ])

    # 数据行
    for r in records:
        task = task_map.get(r.task_id)
        time_start = task.start_time if task else ""
        time_end = task.end_time if task else ""
        writer.writerow([
            r.id,
            r.user_id,
            r.friend_id,
            r.friend_name or "",
            r.chat_title or "",
            r.alias or "",
            r.phone or "",
            r.remark_phone or "",
            f"{time_start} ~ {time_end}",
            r.chat_record_count,
            r.keyword_detected,
            r.detected_keywords or "",
            r.risk_level or "",
            r.trigger_party or "",
            r.risk_category or "",
            r.issue_summary or "",
            r.action_priority or "",
            r.recommended_owner or "",
            r.action_type or "",
            r.follow_up_deadline or "",
            "是" if r.needs_manual_review else "否",
            r.confidence if r.confidence is not None else "",
            r.process_status or "",
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=quality_check_results.csv"}
    )


# === 质检任务查询 API ===

@router.get("/quality-check/tasks")
async def query_quality_check_tasks(
    status: str | None = Query(None, description="任务状态：pending/running/completed/cancelled/error/no_pairs/no_matches"),
    start_time: str | None = Query(None, description="任务发起时间起（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="任务发起时间止（YYYY-MM-DD HH:mm:ss）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """查询质检任务列表，支持分页和状态/时间筛选"""
    async with async_session() as session:
        stmt = select(QualityCheckTask)
        count_stmt = select(func.count()).select_from(QualityCheckTask)

        if status:
            stmt = stmt.where(QualityCheckTask.status == status)
            count_stmt = count_stmt.where(QualityCheckTask.status == status)
        if start_time:
            stmt = stmt.where(QualityCheckTask.created_at >= start_time)
            count_stmt = count_stmt.where(QualityCheckTask.created_at >= start_time)
        if end_time:
            stmt = stmt.where(QualityCheckTask.created_at <= end_time)
            count_stmt = count_stmt.where(QualityCheckTask.created_at <= end_time)

        total = await session.scalar(count_stmt)

        stmt = stmt.order_by(QualityCheckTask.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": [t.to_dict() for t in tasks],
        }


@router.get("/quality-check/tasks/{task_id}")
async def get_quality_check_task_detail(
    task_id: int,
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """获取单个质检任务详情（含统计信息）"""
    async with async_session() as session:
        stmt = select(QualityCheckTask).where(QualityCheckTask.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()

        if not task:
            return {"error": "任务不存在"}

        # 查询该任务下的质检结果统计
        result_count_stmt = select(func.count()).select_from(QualityCheckResult).where(
            QualityCheckResult.task_id == task_id
        )
        result_count = await session.scalar(result_count_stmt)

        risk_dist_stmt = select(
            QualityCheckResult.risk_level, func.count().label("count")
        ).where(QualityCheckResult.task_id == task_id).group_by(QualityCheckResult.risk_level)
        risk_result = await session.execute(risk_dist_stmt)
        risk_distribution = {row.risk_level or "none": row.count for row in risk_result}

        task_dict = task.to_dict()
        task_dict["result_count"] = result_count
        task_dict["risk_distribution"] = risk_distribution

        return task_dict


@router.get("/quality-check/{result_id}/chat-records")
async def get_quality_check_chat_records(
    result_id: int,
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """获取质检结果对应的全部聊天记录

    使用与分析时相同的查询逻辑（get_chat_records_for_quality_check），
    即 end_time 往前推 QUALITY_CHECK_CHAT_DAYS 天，并截取最新 QUALITY_CHECK_MAX_CHAT_RECORDS 条，
    确保展示的聊天记录与 AI 分析时完全一致。
    """
    async with async_session() as session:
        stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        # 从任务表获取 end_time
        task_end_time = None
        if record.task_id:
            task_stmt = select(QualityCheckTask).where(QualityCheckTask.id == record.task_id)
            task_result = await session.execute(task_stmt)
            task = task_result.scalar_one_or_none()
            if task:
                task_end_time = task.end_time

        # 使用与分析时相同的查询函数：end_time 往前推 QUALITY_CHECK_CHAT_DAYS 天 + 条数限制
        chat_records = get_chat_records_for_quality_check(
            user_id=record.user_id,
            friend_id=record.friend_id,
            end_time=task_end_time or "2099-12-31 23:59:59",
        )

        # 计算实际查询时间范围（与分析时一致）
        if task_end_time:
            end_dt = datetime.strptime(task_end_time, "%Y-%m-%d %H:%M:%S")
            actual_start = (end_dt - timedelta(days=settings.QUALITY_CHECK_CHAT_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            actual_start = None

        return {
            "total": len(chat_records),
            "data": chat_records,
            "time_range": {
                "start": actual_start,
                "end": task_end_time,
            },
        }


@router.get("/quality-check/{result_id}")
async def get_quality_check_detail(
    result_id: int,
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """获取单条质检检测结果（包含详情表的大字段）"""
    async with async_session() as session:
        # 查询主表
        stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        # 关联查询详情表（大字段）
        detail_stmt = select(QualityCheckDetail).where(
            QualityCheckDetail.result_id == result_id
        )
        detail_result = await session.execute(detail_stmt)
        detail = detail_result.scalar_one_or_none()

        # 合并返回
        data = record.to_dict()

        # 从任务表获取检测时间范围（优先任务表，兑底旧字段）
        if record.task_id:
            task_stmt = select(QualityCheckTask).where(QualityCheckTask.id == record.task_id)
            task_result = await session.execute(task_stmt)
            task = task_result.scalar_one_or_none()
            if task:
                data["check_time_start"] = task.start_time
                data["check_time_end"] = task.end_time

        if detail:
            data["guidance"] = detail.guidance
            data["keyword_matches"] = detail.keyword_matches
            data["key_evidence"] = detail.key_evidence
            data["raw_response"] = detail.raw_response

        return data


def invalidate_quality_check_stats_cache(user_id: str = None) -> None:
    """清除质检统计缓存"""
    if user_id:
        cache_clear_pattern(f"quality_check:stats:user:{user_id}")
    else:
        # 清除 admin 的缓存（精确匹配）
        cache_delete("quality_check:stats")
        # 清除所有用户的缓存（模式匹配）
        cache_clear_pattern("quality_check:stats:*")


class QualityCheckUpdateRequest(BaseModel):
    risk_level: str | None = None
    remark: str | None = None
    process_status: str | None = None


@router.put("/quality-check/{result_id}")
async def update_quality_check_result(
    result_id: int,
    request: QualityCheckUpdateRequest,
    current_user: dict = Depends(require_permission("update:quality_check")),
):
    """修改质检结果的风险等级、处理状态和备注（带审计日志）

    逻辑说明：
    - 只有当风险等级实际改变时，才更新 modified_risk_level
    - 如果风险等级改回原始值（和 risk_level 相同），则清空 modified_risk_level
    - 备注 modification 不影响 modified_risk_level
    """
    async with async_session() as session:
        # 1. 获取原记录
        stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        # 2. 获取旧值
        old_effective_risk_level = record.modified_risk_level or record.risk_level  # 当前生效的风险等级
        old_original_risk_level = record.risk_level  # AI 原始检测的风险等级
        old_remark = record.remark or ""
        old_process_status = record.process_status or "pending"

        # 3. 确定新值
        new_risk_level = request.risk_level if request.risk_level is not None else old_effective_risk_level
        new_remark = request.remark if request.remark is not None else old_remark
        new_process_status = request.process_status if request.process_status is not None else old_process_status

        # 4. 检查是否有实际修改
        risk_level_changed = new_risk_level != old_effective_risk_level
        remark_changed = new_remark != old_remark
        process_status_changed = new_process_status != old_process_status

        if not risk_level_changed and not remark_changed and not process_status_changed:
            return {"message": "无实际修改", "data": record.to_dict()}

        # 5. 确定 modified_risk_level 的最终值
        # 只有风险等级实际改变时才更新 modified_risk_level
        if risk_level_changed:
            # 风险等级发生了改变，记录到 modified_risk_level
            final_modified_risk_level = new_risk_level
        else:
            # 风险等级未改变，保持原样
            final_modified_risk_level = record.modified_risk_level

        # 6. 写入审计日志
        log = QualityCheckModificationLog(
            result_id=result_id,
            user_id=str(current_user["user_id"]),
            user_name=current_user["username"],
            old_risk_level=old_effective_risk_level,
            new_risk_level=new_risk_level,
            old_remark=old_remark,
            new_remark=new_remark,
            modified_at=to_naive_shanghai(now_shanghai()),
        )
        session.add(log)

        # 7. 更新主记录
        record.remark = new_remark
        record.modified_risk_level = final_modified_risk_level
        record.process_status = new_process_status
        record.modified_at = to_naive_shanghai(now_shanghai())
        record.modified_by = str(current_user["user_id"])
        record.modified_by_name = current_user["username"]

        await session.commit()

        # 8. 清除统计缓存
        invalidate_quality_check_stats_cache()

        return {
            "message": "修改成功",
            "data": record.to_dict(),
        }


@router.get("/quality-check/{result_id}/modification-logs")
async def get_quality_check_modification_logs(
    result_id: int,
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """获取质检结果的修改记录（审计日志）"""
    async with async_session() as session:
        stmt = select(QualityCheckModificationLog).where(
            QualityCheckModificationLog.result_id == result_id
        ).order_by(QualityCheckModificationLog.modified_at.desc())
        result = await session.execute(stmt)
        logs = result.scalars().all()

        return {
            "total": len(logs),
            "data": [log.to_dict() for log in logs],
        }
