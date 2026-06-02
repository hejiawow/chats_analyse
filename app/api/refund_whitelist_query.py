# -*- coding: utf-8 -*-
"""协议话术白名单管理 API"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import RefundWhitelistPattern
from app.services.dependencies import require_permission

router = APIRouter()


class CreatePatternRequest(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=100, description="话术内容")
    description: str | None = Field(None, max_length=200, description="描述说明")


class UpdatePatternRequest(BaseModel):
    pattern: str | None = Field(None, min_length=1, max_length=100, description="话术内容")
    description: str | None = Field(None, max_length=200, description="描述说明")
    is_active: bool | None = Field(None, description="是否启用")


def get_db():
    """获取数据库会话"""
    with Session(sync_engine) as session:
        yield session


@router.get("/refund-whitelist")
async def get_whitelist_patterns(
    session: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("admin:whitelist")),
):
    """获取所有协议话术白名单"""
    patterns = session.query(RefundWhitelistPattern).order_by(
        RefundWhitelistPattern.created_at.desc()
    ).all()
    return {"data": [p.to_dict() for p in patterns]}


@router.post("/refund-whitelist")
async def create_pattern(
    req: CreatePatternRequest,
    session: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("admin:whitelist")),
):
    """新增协议话术"""
    # 检查是否已存在
    existing = session.query(RefundWhitelistPattern).filter(
        RefundWhitelistPattern.pattern == req.pattern
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"话术「{req.pattern}」已存在")

    pattern = RefundWhitelistPattern(
        pattern=req.pattern,
        description=req.description,
        is_active=True,
        created_at=datetime.now(),
    )
    session.add(pattern)
    session.commit()
    session.refresh(pattern)

    return {"data": pattern.to_dict(), "message": "协议话术已创建"}


@router.put("/refund-whitelist/{id}")
async def update_pattern(
    id: int,
    req: UpdatePatternRequest,
    session: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("admin:whitelist")),
):
    """修改协议话术"""
    pattern = session.query(RefundWhitelistPattern).filter(
        RefundWhitelistPattern.id == id
    ).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="协议话术不存在")

    # 更新字段
    if req.pattern is not None:
        # 检查新话术是否已存在（排除自身）
        existing = session.query(RefundWhitelistPattern).filter(
            RefundWhitelistPattern.pattern == req.pattern,
            RefundWhitelistPattern.id != id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"话术「{req.pattern}」已存在")
        pattern.pattern = req.pattern

    if req.description is not None:
        pattern.description = req.description

    if req.is_active is not None:
        pattern.is_active = req.is_active

    pattern.updated_at = datetime.now()
    session.commit()
    session.refresh(pattern)

    return {"data": pattern.to_dict(), "message": "协议话术已更新"}


@router.delete("/refund-whitelist/{id}")
async def delete_pattern(
    id: int,
    session: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("admin:whitelist")),
):
    """删除协议话术"""
    pattern = session.query(RefundWhitelistPattern).filter(
        RefundWhitelistPattern.id == id
    ).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="协议话术不存在")

    session.delete(pattern)
    session.commit()

    return {"message": "协议话术已删除"}


@router.put("/refund-whitelist/{id}/toggle")
async def toggle_pattern(
    id: int,
    session: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("admin:whitelist")),
):
    """启用/禁用协议话术"""
    pattern = session.query(RefundWhitelistPattern).filter(
        RefundWhitelistPattern.id == id
    ).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="协议话术不存在")

    pattern.is_active = not pattern.is_active
    pattern.updated_at = datetime.now()
    session.commit()
    session.refresh(pattern)

    status_text = "启用" if pattern.is_active else "禁用"
    return {"data": pattern.to_dict(), "message": f"协议话术已{status_text}"}