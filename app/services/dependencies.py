# -*- coding: utf-8 -*-
"""FastAPI 依赖注入鉴权中间件"""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth import decode_access_token

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    从请求 Header 的 Authorization: Bearer <token> 中解析 JWT。
    返回 {user_id, username, permissions}，无效或过期则拒绝。
    """
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    username = payload.get("username")
    permissions = payload.get("permissions", [])

    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 格式无效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": int(user_id),
        "username": username,
        "permissions": permissions,
    }


def require_permission(permission: str):
    """
    权限校验依赖工厂。
    用法：user = Depends(require_permission("write:trigger"))
    拥有 "admin" 角色的用户自动通过所有权限校验。
    """
    def _check(user: dict = Depends(get_current_user)) -> dict:
        if "admin:all" in user.get("permissions", []):
            return user
        if permission not in user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要权限 [{permission}]",
            )
        return user
    return _check


def require_any_permission(*permissions: str):
    """
    满足任一权限即可通过。
    用法：user = Depends(require_any_permission("read:cases", "read:journey"))
    """
    def _check(user: dict = Depends(get_current_user)) -> dict:
        if "admin:all" in user.get("permissions", []):
            return user
        user_perms = set(user.get("permissions", []))
        if not user_perms.intersection(set(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要权限 [{', '.join(permissions)}] 之一",
            )
        return user
    return _check


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """仅要求登录，不检查具体权限（用于 /api/auth/me 等端点）"""
    return user
