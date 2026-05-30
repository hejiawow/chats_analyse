# -*- coding: utf-8 -*-
"""质检检测结果查询 API"""
import io
import csv
from datetime import datetime
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.result import QualityCheckResult
from app.services.dependencies import require_permission, get_current_user
from app.services.cache import cache_get, cache_set, cache_delete, cache_clear_pattern
from app.services.hujing_api import get_chat_records

_STATS_CACHE_TTL = 300  # 统计缓存：5 分钟
_STATS_CACHE_KEY = "quality_check:stats"

router = APIRouter()


def _build_time_filter(start_time: str | None, end_time: str | None):
    """构建检测时间范围筛选条件

    筛选逻辑：检测时间范围与筛选时间范围有交集
    - check_time_start <= end_time（检测开始时间在筛选结束时间之前）
    - check_time_end >= start_time（检测结束时间在筛选开始时间之后）
    """
    conditions = []
    if start_time:
        conditions.append(QualityCheckResult.check_time_end >= start_time)
    if end_time:
        conditions.append(QualityCheckResult.check_time_start <= end_time)
    return and_(*conditions) if conditions else None


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
    """查询质检检测结果，支持筛选。非 admin 用户只能查看自己的数据。

    时间筛选：按检测时间范围（check_time_start/check_time_end）筛选，
    筛选逻辑为检测时间范围与筛选时间范围有交集。
    """
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

        # 按检测时间范围筛选
        time_filter = _build_time_filter(start_time, end_time)
        if time_filter is not None:
            stmt = stmt.where(time_filter)

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
        if time_filter is not None:
            count_stmt = count_stmt.where(time_filter)

        total = await session.scalar(count_stmt)

        # 分页数据
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": [r.to_dict() for r in records],
        }


@router.get("/quality-check/stats")
async def get_quality_check_stats(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    keyword: str | None = Query(None, description="关键词"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    current_user: dict = Depends(require_permission("read:referral")),
):
    """获取质检结果统计：总数、风险分布、关键词频次（支持筛选）

    时间筛选：按检测时间范围（check_time_start/check_time_end）筛选
    注意：风险等级筛选不影响统计，只影响表格
    """
    # 权限控制：非 admin 用户只能查看自己的数据
    user_id_filter = None
    if "admin:all" not in current_user.get("permissions", []):
        user_id_filter = str(current_user["user_id"])
    elif user_id:
        # admin 用户可以指定查看特定用户
        user_id_filter = user_id

    # 判断是否有筛选条件（影响缓存策略）
    has_filters = user_id_filter or friend_id or keyword or start_time or end_time

    # 缓存策略：无筛选条件时使用缓存，有筛选条件时不缓存
    cache_key = _STATS_CACHE_KEY
    if user_id_filter and "admin:all" in current_user.get("permissions", []):
        cache_key = f"{_STATS_CACHE_KEY}:user:{user_id_filter}"

    # 只有无任何筛选条件时才使用缓存
    if not has_filters:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    # 构建检测时间范围筛选条件
    time_filter = _build_time_filter(start_time, end_time)

    async with async_session() as session:
        # 总数统计
        count_stmt = select(func.count()).select_from(QualityCheckResult)
        if user_id_filter:
            count_stmt = count_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            count_stmt = count_stmt.where(QualityCheckResult.friend_id == friend_id)
        if keyword:
            count_stmt = count_stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{keyword}%"))
        if time_filter is not None:
            count_stmt = count_stmt.where(time_filter)
        total = await session.scalar(count_stmt)

        # 风险等级分布
        risk_stmt = select(
            QualityCheckResult.risk_level,
            func.count().label("count")
        ).group_by(QualityCheckResult.risk_level)
        if user_id_filter:
            risk_stmt = risk_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            risk_stmt = risk_stmt.where(QualityCheckResult.friend_id == friend_id)
        if keyword:
            risk_stmt = risk_stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{keyword}%"))
        if time_filter is not None:
            risk_stmt = risk_stmt.where(time_filter)
        risk_result = await session.execute(risk_stmt)
        risk_distribution = {row.risk_level or "none": row.count for row in risk_result}

        # 关键词频次统计
        keyword_stmt = select(QualityCheckResult.detected_keywords)
        if user_id_filter:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.user_id == user_id_filter)
        if friend_id is not None:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.friend_id == friend_id)
        if keyword:
            keyword_stmt = keyword_stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{keyword}%"))
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
    risk_level: str | None = Query(None, description="风险等级"),
    keyword: str | None = Query(None, description="关键词内容（模糊匹配）"),
    start_time: str | None = Query(None, description="开始时间（YYYY-MM-DD HH:mm:ss）"),
    end_time: str | None = Query(None, description="结束时间（YYYY-MM-DD HH:mm:ss）"),
    limit: int = Query(10000, ge=1, le=50000, description="导出数量上限"),
    current_user: dict = Depends(require_permission("read:referral")),
):
    """导出质检结果为 CSV 文件（带数量限制）

    时间筛选：按检测时间范围（check_time_start/check_time_end）筛选
    """
    # 非 admin 用户自动过滤
    if "admin:all" not in current_user.get("permissions", []):
        user_id = str(current_user["user_id"])

    # 构建检测时间范围筛选条件
    time_filter = _build_time_filter(start_time, end_time)

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
        if time_filter is not None:
            stmt = stmt.where(time_filter)
        stmt = stmt.order_by(QualityCheckResult.created_at.desc())
        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        records = result.scalars().all()

    # 构建 CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # 表头
    writer.writerow([
        "ID", "销售ID", "好友ID", "好友姓名", "好友备注", "好友别名", "绑定手机号", "备注手机号",
        "检测时间范围", "聊天记录数",
        "关键词检测", "检测关键词", "风险等级", "风险类别",
        "风险描述", "建议措施", "创建时间"
    ])

    # 数据行
    for r in records:
        writer.writerow([
            r.id,
            r.user_id,
            r.friend_id,
            r.friend_name or "",
            r.chat_title or "",
            r.alias or "",
            r.phone or "",
            r.remark_phone or "",
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


@router.get("/quality-check/{result_id}/chat-records")
async def get_quality_check_chat_records(
    result_id: int,
    current_user: dict = Depends(require_permission("read:referral")),
):
    """获取质检结果对应的全部聊天记录"""
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

        # 打印调试信息
        print(f"[DEBUG] get_chat_records params: user_id={record.user_id}, friend_id={record.friend_id}, start={record.check_time_start}, end={record.check_time_end}")

        # 获取聊天记录
        chat_records = get_chat_records(
            user_id=record.user_id,
            friend_id=record.friend_id,
            start_time=record.check_time_start or "2000-01-01 00:00:00",
            end_time=record.check_time_end or "2099-12-31 23:59:59",
        )

        print(f"[DEBUG] get_chat_records returned: {len(chat_records)} records")

        return {
            "total": len(chat_records),
            "data": chat_records,
            "time_range": {
                "start": record.check_time_start,
                "end": record.check_time_end,
            },
        }


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