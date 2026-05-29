# -*- coding: utf-8 -*-
"""质检检测结果查询 API"""
import io
import csv
from datetime import datetime
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.result import QualityCheckResult
from app.services.dependencies import require_permission, get_current_user
from app.services.cache import cache_get, cache_set, cache_delete, cache_clear_pattern

_STATS_CACHE_TTL = 300  # 统计缓存：5 分钟
_STATS_CACHE_KEY = "quality_check:stats"

router = APIRouter()


@router.get("/quality-check")
async def query_quality_check_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    risk_level: str | None = Query(None, description="风险等级：high/medium/low/none"),
    keyword: str | None = Query(None, description="关键词内容（模糊匹配）"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("read:referral")),
):
    """查询质检检测结果，支持筛选。非 admin 用户只能查看自己的数据。"""
    # 非 admin 用户自动过滤到当前用户的 user_id
    if "admin:all" not in current_user.get("permissions", []):
        user_id = str(current_user["user_id"])

    async with async_session() as session:
        stmt = select(QualityCheckResult)
        if user_id:
            stmt = stmt.where(QualityCheckResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(QualityCheckResult.friend_id == friend_id)
        if risk_level:
            stmt = stmt.where(QualityCheckResult.risk_level == risk_level)
        if keyword:
            stmt = stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{keyword}%"))
        if start_time:
            stmt = stmt.where(QualityCheckResult.created_at >= datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"))
        if end_time:
            stmt = stmt.where(QualityCheckResult.created_at <= datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S"))

        stmt = stmt.order_by(QualityCheckResult.created_at.desc())

        # 总数
        count_stmt = select(func.count()).select_from(QualityCheckResult)
        if user_id:
            count_stmt = count_stmt.where(QualityCheckResult.user_id == user_id)
        if friend_id is not None:
            count_stmt = count_stmt.where(QualityCheckResult.friend_id == friend_id)
        if risk_level:
            count_stmt = count_stmt.where(QualityCheckResult.risk_level == risk_level)
        if keyword:
            count_stmt = count_stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{keyword}%"))
        if start_time:
            count_stmt = count_stmt.where(QualityCheckResult.created_at >= datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"))
        if end_time:
            count_stmt = count_stmt.where(QualityCheckResult.created_at <= datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S"))

        total = await session.scalar(count_stmt)

        # 分页数据
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()

        return {
            "total": total,
            "page": page_size,
            "page_size": page_size,
            "data": [r.to_dict() for r in records],
        }


@router.get("/quality-check/stats")
async def get_quality_check_stats(
    current_user: dict = Depends(require_permission("read:referral")),
):
    """获取质检结果统计：总数、风险分布、关键词频次（带缓存）"""
    user_id_filter = None
    if "admin:all" not in current_user.get("permissions", []):
        user_id_filter = str(current_user["user_id"])

    # 构建缓存 key（包含 user_id_filter）
    cache_key = _STATS_CACHE_KEY
    if user_id_filter:
        cache_key = f"{_STATS_CACHE_KEY}:user:{user_id_filter}"

    # 尝试从缓存获取
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    async with async_session() as session:
        # 总数统计
        count_stmt = select(func.count()).select_from(QualityCheckResult)
        if user_id_filter:
            count_stmt = count_stmt.where(QualityCheckResult.user_id == user_id_filter)
        total = await session.scalar(count_stmt)

        # 风险等级分布
        risk_stmt = select(
            QualityCheckResult.risk_level,
            func.count().label("count")
        ).group_by(QualityCheckResult.risk_level)
        if user_id_filter:
            risk_stmt = risk_stmt.where(QualityCheckResult.user_id == user_id_filter)
        risk_result = await session.execute(risk_stmt)
        risk_distribution = {row.risk_level or "none": row.count for row in risk_result}

        # 关键词频次统计
        keyword_stmt = select(QualityCheckResult.detected_keywords)
        if user_id_filter:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.user_id == user_id_filter)
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
            "keyword_frequency": keyword_frequency,
        }

        # 存入缓存
        cache_set(cache_key, result, _STATS_CACHE_TTL)

        return result


@router.get("/quality-check/export")
async def export_quality_check_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    risk_level: str | None = Query(None, description="风险等级"),
    keyword: str | None = Query(None, description="关键词内容（模糊匹配）"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    limit: int = Query(10000, ge=1, le=50000, description="导出数量上限"),
    current_user: dict = Depends(require_permission("read:referral")),
):
    """导出质检结果为 CSV 文件（带数量限制）"""
    # 非 admin 用户自动过滤
    if "admin:all" not in current_user.get("permissions", []):
        user_id = str(current_user["user_id"])

    async with async_session() as session:
        stmt = select(QualityCheckResult)
        if user_id:
            stmt = stmt.where(QualityCheckResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(QualityCheckResult.friend_id == friend_id)
        if risk_level:
            stmt = stmt.where(QualityCheckResult.risk_level == risk_level)
        if keyword:
            stmt = stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{keyword}%"))
        if start_time:
            stmt = stmt.where(QualityCheckResult.created_at >= datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"))
        if end_time:
            stmt = stmt.where(QualityCheckResult.created_at <= datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S"))
        stmt = stmt.order_by(QualityCheckResult.created_at.desc())
        stmt = stmt.limit(limit)  # 添加限制

        result = await session.execute(stmt)
        records = result.scalars().all()

    # 构建 CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # 表头
    writer.writerow([
        "ID", "销售ID", "好友ID", "检测时间范围", "聊天记录数",
        "关键词检测", "检测关键词", "风险等级", "风险类别",
        "风险描述", "建议措施", "创建时间"
    ])

    # 数据行
    for r in records:
        writer.writerow([
            r.id,
            r.user_id,
            r.friend_id,
            f"{r.check_time_start} ~ {r.check_time_end}",
            r.chat_record_count,
            r.keyword_detected,
            r.detected_keywords or "",
            r.risk_level or "",
            r.risk_category or "",
            r.risk_description or "",
            r.suggested_action or "",
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=quality_check_results.csv"}
    )


@router.get("/quality-check/{result_id}")
async def get_quality_check_detail(
    result_id: int,
    current_user: dict = Depends(require_permission("read:referral")),
):
    """获取单条质检检测结果"""
    async with async_session() as session:
        stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        # 非 admin 用户只能查看自己的数据
        if "admin:all" not in current_user.get("permissions", []):
            if record.user_id != str(current_user["user_id"]):
                return {"error": "无权查看此记录"}

        return record.to_dict()


def invalidate_quality_check_stats_cache(user_id: str = None) -> None:
    """清除质检统计缓存"""
    if user_id:
        cache_clear_pattern(f"quality_check:stats:user:{user_id}")
    else:
        # 清除 admin 的缓存（精确匹配）
        cache_delete("quality_check:stats")
        # 清除所有用户的缓存（模式匹配）
        cache_clear_pattern("quality_check:stats:*")