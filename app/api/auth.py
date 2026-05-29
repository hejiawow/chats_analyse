# -*- coding: utf-8 -*-
"""认证相关 API — 登录、获取当前用户信息"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.services.auth import authenticate_user
from app.services.dependencies import get_current_user, require_auth

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(req: LoginRequest):
    """
    用户登录。验证用户名和密码，返回 JWT Token 及用户信息。
    """
    try:
        logger.info(f"Login attempt for user: {req.username}")
        async with async_session() as db:
            result = await authenticate_user(db, req.username, req.password)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Login error: {e}")
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
