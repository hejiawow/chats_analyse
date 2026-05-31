# -*- coding: utf-8 -*-
"""认证相关 API — 登录、获取当前用户信息"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.services.auth import authenticate_user
from app.services.dependencies import get_current_user, require_auth
from app.services.audit_service import audit_service

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(req: LoginRequest, request: Request):
    """
    用户登录。验证用户名和密码，返回 JWT Token 及用户信息。
    """
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    try:
        logger.info(f"Login attempt for user: {req.username}")
        async with async_session() as db:
            result = await authenticate_user(db, req.username, req.password)

        if not result:
            # 记录登录失败日志
            await audit_service.log_login(
                user_id=None,
                username=req.username,
                ip_address=ip_address,
                success=False,
                failure_reason="用户名或密码错误",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 记录登录成功日志
        await audit_service.log_login(
            user_id=result["user_id"],
            username=result["username"],
            ip_address=ip_address,
            success=True,
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Login error: {e}")
        # 记录登录异常日志
        await audit_service.log_login(
            user_id=None,
            username=req.username,
            ip_address=ip_address,
            success=False,
            failure_reason=f"{type(e).__name__}: {e}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {type(e).__name__}: {e}",
        )


@router.get("/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    """获取当前登录用户的信息"""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "permissions": user["permissions"],
    }
