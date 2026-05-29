# -*- coding: utf-8 -*-
"""用户管理 API — 增删改查、角色分配"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.auth import User, Role, UserRole
from app.services.auth import hash_password
from app.services.dependencies import require_permission

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str = "active"


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None


class AssignRolesRequest(BaseModel):
    role_ids: list[int]


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("admin:user")),
):
    """获取用户列表（分页）"""
    async with async_session() as db:
        # Count
        count_stmt = select(func.count(User.id))
        if username:
            count_stmt = count_stmt.where(User.username.ilike(f"%{username}%"))
        if status:
            count_stmt = count_stmt.where(User.status == status)
        total = (await db.execute(count_stmt)).scalar()

        # Query
        stmt = select(User).order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        if username:
            stmt = stmt.where(User.username.ilike(f"%{username}%"))
        if status:
            stmt = stmt.where(User.status == status)
        result = await db.execute(stmt)
        users = result.scalars().all()

        # Fetch role names for each user
        user_list = []
        for u in users:
            role_stmt = select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)
            role_result = await db.execute(role_stmt)
            roles = role_result.scalars().all()
            user_list.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "phone": u.phone,
                "status": u.status,
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "roles": [r.name for r in roles],
                "role_names": [r.name for r in roles],
            })

        return {"data": user_list, "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: dict = Depends(require_permission("admin:user")),
):
    """获取用户详情"""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        role_stmt = select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        role_result = await db.execute(role_stmt)
        roles = role_result.scalars().all()

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "status": user.status,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "roles": [r.name for r in roles],
        }


@router.post("/users", status_code=201)
async def create_user(
    req: CreateUserRequest,
    current_user: dict = Depends(require_permission("admin:user")),
):
    """创建用户"""
    async with async_session() as db:
        # Check uniqueness
        existing = await db.execute(select(User).where(User.username == req.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户名已存在")

        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            email=req.email,
            phone=req.phone,
            status=req.status,
            created_at=datetime.now(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return {"id": user.id, "username": user.username, "status": user.status}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    req: UpdateUserRequest,
    current_user: dict = Depends(require_permission("admin:user")),
):
    """更新用户信息"""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if req.email is not None:
            user.email = req.email
        if req.phone is not None:
            user.phone = req.phone
        if req.status is not None:
            user.status = req.status

        await db.commit()
        return {"id": user.id, "username": user.username, "status": user.status}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: dict = Depends(require_permission("admin:user")),
):
    """删除用户"""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # Delete role bindings first
        await db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
        await db.delete(user)
        await db.commit()
        return {"status": "ok"}


@router.post("/users/{user_id}/roles")
async def assign_user_roles(
    user_id: int,
    req: AssignRolesRequest,
    current_user: dict = Depends(require_permission("admin:user")),
):
    """分配用户角色（替换式）"""
    async with async_session() as db:
        # Check user exists
        result = await db.execute(select(User).where(User.id == user_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="用户不存在")

        # Check all roles exist
        role_result = await db.execute(select(Role).where(Role.id.in_(req.role_ids)))
        found_roles = role_result.scalars().all()
        if len(found_roles) != len(req.role_ids):
            raise HTTPException(status_code=400, detail="部分角色不存在")

        # Replace roles
        await db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
        for role_id in req.role_ids:
            db.add(UserRole(user_id=user_id, role_id=role_id))
        await db.commit()

        return {"status": "ok", "role_ids": req.role_ids}
