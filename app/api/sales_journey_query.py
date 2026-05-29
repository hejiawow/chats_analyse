# -*- coding: utf-8 -*-
"""成交案例复盘结果查询 API"""
import os
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func

from app.models.database import async_session
from app.models.result import SalesJourneyResult
from app.services.hujing_api import get_chat_records
from app.services.html_exporter import generate_html_report

router = APIRouter()


@router.get("/sales-journeys")
async def query_sales_journey_results(
    user_id: str | None = Query(None, description="销售ID"),
    friend_id: int | None = Query(None, description="好友ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询成交案例复盘结果，支持筛选"""
    async with async_session() as session:
        stmt = select(SalesJourneyResult)
        if user_id:
            stmt = stmt.where(SalesJourneyResult.user_id == user_id)
        if friend_id is not None:
            stmt = stmt.where(SalesJourneyResult.friend_id == friend_id)

        stmt = stmt.order_by(SalesJourneyResult.created_at.desc())

        # 总数
        count_stmt = select(func.count()).select_from(SalesJourneyResult)
        if user_id:
            count_stmt = count_stmt.where(SalesJourneyResult.user_id == user_id)
        if friend_id is not None:
            count_stmt = count_stmt.where(SalesJourneyResult.friend_id == friend_id)

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


@router.get("/sales-journeys/{result_id}")
async def get_sales_journey_detail(result_id: int):
    """获取单条成交案例复盘详情"""
    async with async_session() as session:
        stmt = select(SalesJourneyResult).where(SalesJourneyResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        return record.to_dict()


@router.get("/sales-journeys/{result_id}/download")
async def download_sales_journey_report(result_id: int):
    """下载成交案例 HTML 报告"""
    async with async_session() as session:
        stmt = select(SalesJourneyResult).where(SalesJourneyResult.id == result_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}

        if record.status in ("no_chat", "failed"):
            return {"error": "该记录无分析结果"}

        # 获取分析结果
        analysis_result = record.analysis_result or {}
        friend_nick = record.friend_nick or "成交案例"

        # 拉取聊天记录
        try:
            chat_records = get_chat_records(record.user_id, record.friend_id)
        except Exception:
            chat_records = []

        # 生成 HTML 报告（保存到桌面）
        export_filename = f"{friend_nick}_成交案例报告.html"
        export_path = os.path.join("C:/Users/23824/Desktop", export_filename)
        file_path = generate_html_report(
            analysis_result=analysis_result,
            chat_records=chat_records,
            friend_nick=friend_nick,
            export_path=export_path,
        )

        # 返回文件下载
        return FileResponse(
            path=file_path,
            filename=export_filename,
            media_type="text/html",
        )
