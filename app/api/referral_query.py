# -*- coding: utf-8 -*-
"""转介绍检测结果查询 API"""
from datetime import datetime
from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.result import ReferralResult
from app.services.dependencies import require_permission, get_current_user

router = APIRouter()


@router.get("/referral")
async def query_referral_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    status: str | None = Query(None, description="结果状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("read:referral")),
):
    """查询转介绍检测结果，支持筛选。非 admin 用户只能查看自己的数据。"""
    # 非 admin 用户自动过滤到当前用户的 user_id
    if "admin:all" not in current_user.get("permissions", []):
        user_id = str(current_user["user_id"])

    async with async_session() as session:
        stmt = select(ReferralResult)
        if user_id:
            stmt = stmt.where(ReferralResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(ReferralResult.friend_id == friend_id)

        stmt = stmt.order_by(ReferralResult.created_at.desc())

        # 总数
        count_stmt = select(func.count()).select_from(ReferralResult)
        if user_id:
            count_stmt = count_stmt.where(ReferralResult.user_id == user_id)
        if friend_id is not None:
            count_stmt = count_stmt.where(ReferralResult.friend_id == friend_id)

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


@router.get("/referral/{result_id}")
async def get_referral_detail(
    result_id: int,
    current_user: dict = Depends(require_permission("read:referral")),
):
    """获取单条转介绍检测结果"""
    async with async_session() as session:
        stmt = select(ReferralResult).where(ReferralResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        # 非 admin 用户只能查看自己的数据
        if "admin:all" not in current_user.get("permissions", []):
            if record.user_id != str(current_user["user_id"]):
                return {"error": "无权查看此记录"}

        return record.to_dict()
