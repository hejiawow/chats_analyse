# -*- coding: utf-8 -*-
"""风险关键词配置管理 API"""
from datetime import datetime
from fastapi import APIRouter, Query, Depends, HTTPException, Body, Request
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.result import RiskKeyword
from app.services.dependencies import require_permission, get_current_user
from app.services.audit_service import audit_service

router = APIRouter()


@router.get("/keywords/active")
async def list_active_keywords(
    current_user: dict = Depends(require_permission("read:quality_check")),
):
    """获取启用的关键词列表（用于筛选下拉框）"""
    async with async_session() as session:
        stmt = select(RiskKeyword).where(RiskKeyword.is_active == True)
        stmt = stmt.order_by(RiskKeyword.keyword)
        result = await session.execute(stmt)
        records = result.scalars().all()

        keywords = [r.keyword for r in records]

        # 如果数据库没有数据，返回默认关键词
        if not keywords:
            keywords = [
                "退款", "退费", "退掉", "退钱", "返还",
                "投诉", "举报", "告你们", "投诉你们",
                "取消订单", "退订", "不买了", "不想买了",
                "工商", "消费者协会", "消协", "12315", "市场监管局",
                "骗人", "骗子", "欺诈", "虚假宣传", "承诺没兑现",
            ]

        return {"data": keywords}


@router.get("/keywords")
async def list_keywords(
    category: str | None = Query(None, description="类别筛选"),
    is_active: bool | None = Query(None, description="是否启用"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_permission("admin:all")),
):
    """获取关键词列表（需要管理员权限）"""
    async with async_session() as session:
        stmt = select(RiskKeyword)
        if category:
            stmt = stmt.where(RiskKeyword.category == category)
        if is_active is not None:
            stmt = stmt.where(RiskKeyword.is_active == is_active)

        stmt = stmt.order_by(RiskKeyword.category, RiskKeyword.keyword)

        # 总数
        count_stmt = select(func.count()).select_from(RiskKeyword)
        if category:
            count_stmt = count_stmt.where(RiskKeyword.category == category)
        if is_active is not None:
            count_stmt = count_stmt.where(RiskKeyword.is_active == is_active)
        total = await session.scalar(count_stmt)

        # 分页
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": [r.to_dict() for r in records],
        }


@router.post("/keywords")
async def add_keyword(
    request: Request,
    keyword: str = Body(..., embed=True),
    category: str = Body(..., embed=True),
    severity: str = Body("medium", embed=True),
    current_user: dict = Depends(require_permission("admin:all")),
):
    """添加关键词（需要管理员权限）"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    async with async_session() as session:
        # 检查是否已存在
        stmt = select(RiskKeyword).where(RiskKeyword.keyword == keyword)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(status_code=400, detail=f"关键词已存在: {keyword}")

        # 创建新关键词
        new_kw = RiskKeyword(
            keyword=keyword,
            category=category,
            severity=severity,
            is_active=True,
            created_at=datetime.now(),
        )
        session.add(new_kw)
        await session.commit()
        await session.refresh(new_kw)

        # 记录审计日志
        await audit_service.log_keyword_change(
            operator_id=current_user["user_id"],
            operator_name=current_user["username"],
            action="create",
            keyword_id=new_kw.id,
            keyword=keyword,
            changes={"category": category, "severity": severity},
            ip_address=ip_address,
        )

        return {"status": "success", "keyword": new_kw.to_dict()}


@router.put("/keywords/{keyword_id}")
async def update_keyword(
    keyword_id: int,
    request: Request,
    keyword: str | None = Body(None, embed=True),
    category: str | None = Body(None, embed=True),
    severity: str | None = Body(None, embed=True),
    is_active: bool | None = Body(None, embed=True),
    current_user: dict = Depends(require_permission("admin:all")),
):
    """更新关键词（需要管理员权限）"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    async with async_session() as session:
        stmt = select(RiskKeyword).where(RiskKeyword.id == keyword_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="关键词不存在")

        # 记录变更
        changes = {}
        if keyword is not None:
            changes["keyword"] = {"old": record.keyword, "new": keyword}
            record.keyword = keyword
        if category is not None:
            changes["category"] = {"old": record.category, "new": category}
            record.category = category
        if severity is not None:
            changes["severity"] = {"old": record.severity, "new": severity}
            record.severity = severity
        if is_active is not None:
            changes["is_active"] = {"old": record.is_active, "new": is_active}
            record.is_active = is_active
        record.updated_at = datetime.now()

        await session.commit()

        # 记录审计日志
        if changes:
            await audit_service.log_keyword_change(
                operator_id=current_user["user_id"],
                operator_name=current_user["username"],
                action="update",
                keyword_id=keyword_id,
                keyword=record.keyword,
                changes=changes,
                ip_address=ip_address,
            )

        return {"status": "success", "keyword": record.to_dict()}


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(
    keyword_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("admin:all")),
):
    """删除关键词（需要管理员权限）"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    async with async_session() as session:
        stmt = select(RiskKeyword).where(RiskKeyword.id == keyword_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="关键词不存在")

        keyword_text = record.keyword

        # 记录审计日志（删除前）
        await audit_service.log_keyword_change(
            operator_id=current_user["user_id"],
            operator_name=current_user["username"],
            action="delete",
            keyword_id=keyword_id,
            keyword=keyword_text,
            ip_address=ip_address,
        )

        await session.delete(record)
        await session.commit()

        return {"status": "success", "message": "关键词已删除"}


@router.post("/keywords/init-default")
async def init_default_keywords(
    current_user: dict = Depends(require_permission("admin:all")),
):
    """初始化默认关键词（需要管理员权限）"""
    default_keywords = [
        {"keyword": "退款", "category": "refund", "severity": "high"},
        {"keyword": "退费", "category": "refund", "severity": "high"},
        {"keyword": "退掉", "category": "refund", "severity": "medium"},
        {"keyword": "退钱", "category": "refund", "severity": "medium"},
        {"keyword": "返还", "category": "refund", "severity": "medium"},
        {"keyword": "投诉", "category": "complaint", "severity": "high"},
        {"keyword": "举报", "category": "complaint", "severity": "high"},
        {"keyword": "告你们", "category": "complaint", "severity": "high"},
        {"keyword": "投诉你们", "category": "complaint", "severity": "high"},
        {"keyword": "取消订单", "category": "order_cancel", "severity": "medium"},
        {"keyword": "退订", "category": "order_cancel", "severity": "medium"},
        {"keyword": "不买了", "category": "order_cancel", "severity": "medium"},
        {"keyword": "不想买了", "category": "order_cancel", "severity": "medium"},
        {"keyword": "工商", "category": "regulatory", "severity": "high"},
        {"keyword": "消费者协会", "category": "regulatory", "severity": "high"},
        {"keyword": "消协", "category": "regulatory", "severity": "high"},
        {"keyword": "12315", "category": "regulatory", "severity": "high"},
        {"keyword": "市场监管局", "category": "regulatory", "severity": "high"},
        {"keyword": "骗人", "category": "fraud", "severity": "medium"},
        {"keyword": "骗子", "category": "fraud", "severity": "medium"},
        {"keyword": "欺诈", "category": "fraud", "severity": "high"},
        {"keyword": "虚假宣传", "category": "fraud", "severity": "high"},
        {"keyword": "承诺没兑现", "category": "fraud", "severity": "medium"},
    ]

    async with async_session() as session:
        added = 0
        skipped = 0
        for kw in default_keywords:
            stmt = select(RiskKeyword).where(RiskKeyword.keyword == kw["keyword"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            new_kw = RiskKeyword(
                keyword=kw["keyword"],
                category=kw["category"],
                severity=kw["severity"],
                is_active=True,
                created_at=datetime.now(),
            )
            session.add(new_kw)
            added += 1

        await session.commit()

        return {
            "status": "success",
            "added": added,
            "skipped": skipped,
            "total": added + skipped,
        }