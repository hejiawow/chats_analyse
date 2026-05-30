# -*- coding: utf-8 -*-
"""角色管理 API — 增删改查"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.auth import Role, UserRole
from app.services.dependencies import require_permission
from app.services.audit_service import audit_service

router = APIRouter()


class CreateRoleRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: list[str] = []


class UpdateRoleRequest(BaseModel):
    description: Optional[str] = None
    permissions: Optional[list[str]] = None


@router.get("/roles")
async def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("admin:role")),
):
    """获取角色列表（分页）"""
    async with async_session() as db:
        total = (await db.execute(select(func.count(Role.id)))).scalar()
        stmt = select(Role).order_by(Role.id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        roles = result.scalars().all()

        return {
            "data": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "permissions": r.permissions or [],
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in roles
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.get("/roles/{role_id}")
async def get_role(
    role_id: int,
    current_user: dict = Depends(require_permission("admin:role")),
):
    """获取角色详情"""
    async with async_session() as db:
        result = await db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions or [],
            "created_at": role.created_at.isoformat() if role.created_at else None,
        }


@router.post("/roles", status_code=201)
async def create_role(
    req: CreateRoleRequest,
    request: Request,
    current_user: dict = Depends(require_permission("admin:role")),
):
    """创建角色"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    async with async_session() as db:
        existing = await db.execute(select(Role).where(Role.name == req.name))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="角色名称已存在")

        role = Role(
            name=req.name,
            description=req.description,
            permissions=req.permissions,
            created_at=datetime.now(),
        )
        db.add(role)
        await db.commit()
        await db.refresh(role)

        # 记录审计日志
        await audit_service.log_create_role(
            operator_id=current_user["user_id"],
            operator_name=current_user["username"],
            role_id=role.id,
            role_name=role.name,
            permissions=req.permissions,
            ip_address=ip_address,
        )

        return {"id": role.id, "name": role.name}


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    req: UpdateRoleRequest,
    request: Request,
    current_user: dict = Depends(require_permission("admin:role")),
):
    """更新角色"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    async with async_session() as db:
        result = await db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 记录变更
        changes = {}
        if req.description is not None:
            changes["description"] = {"old": role.description, "new": req.description}
            role.description = req.description
        if req.permissions is not None:
            changes["permissions"] = {"old": role.permissions or [], "new": req.permissions}
            role.permissions = req.permissions

        await db.commit()

        # 记录审计日志
        if changes:
            await audit_service.log_update_role(
                operator_id=current_user["user_id"],
                operator_name=current_user["username"],
                role_id=role_id,
                role_name=role.name,
                changes=changes,
                ip_address=ip_address,
            )

        return {"id": role.id, "name": role.name}


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("admin:role")),
):
    """删除角色"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    async with async_session() as db:
        result = await db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        role_name = role.name

        # 记录审计日志（删除前）
        await audit_service.log_delete_role(
            operator_id=current_user["user_id"],
            operator_name=current_user["username"],
            role_id=role_id,
            role_name=role_name,
            ip_address=ip_address,
        )

        # Delete user-role bindings
        await db.execute(UserRole.__table__.delete().where(UserRole.role_id == role_id))
        await db.delete(role)
        await db.commit()
        return {"status": "ok"}
