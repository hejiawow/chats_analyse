# -*- coding: utf-8 -*-
"""督学跟进合规检测结果查询 API"""
from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.models.database import async_session
from app.models.result import FollowUpComplianceResult

router = APIRouter()


@router.get("/follow-up")
async def query_follow_up_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    is_compliant: str | None = Query(None, description="合规状态: compliant / non_compliant"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询督学跟进合规检测结果，支持筛选"""
    async with async_session() as session:
        stmt = select(FollowUpComplianceResult)
        if user_id:
            stmt = stmt.where(FollowUpComplianceResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(FollowUpComplianceResult.friend_id == friend_id)
        if is_compliant:
            stmt = stmt.where(FollowUpComplianceResult.is_compliant == is_compliant)

        stmt = stmt.order_by(FollowUpComplianceResult.created_at.desc())

        # 总数
        count_stmt = select(func.count()).select_from(FollowUpComplianceResult)
        if user_id:
            count_stmt = count_stmt.where(FollowUpComplianceResult.user_id == user_id)
        if friend_id is not None:
            count_stmt = count_stmt.where(FollowUpComplianceResult.friend_id == friend_id)
        if is_compliant:
            count_stmt = count_stmt.where(FollowUpComplianceResult.is_compliant == is_compliant)

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


@router.get("/follow-up/{result_id}")
async def get_follow_up_detail(result_id: int):
    """获取单条督学跟进合规检测结果"""
    async with async_session() as session:
        stmt = select(FollowUpComplianceResult).where(FollowUpComplianceResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        return record.to_dict()
