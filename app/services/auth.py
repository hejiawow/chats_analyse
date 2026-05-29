# -*- coding: utf-8 -*-
"""认证服务 — JWT 签发/验证、密码校验"""
import time
from datetime import datetime, timezone
from typing import Optional

import jwt
from datetime import datetime, timezone
from typing import Optional

import bcrypt as bcrypt_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from app.models.auth import User, Role, UserRole

# JWT 配置
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = 86400  # 24 小时


# ─── 密码工具 ───────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    try:
        return bcrypt_lib.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8'),
        )
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    """生成密码哈希（用于初始化/重置密码）"""
    return bcrypt_lib.hashpw(plain_password.encode('utf-8'), bcrypt_lib.gensalt()).decode('utf-8')


# ─── JWT 工具 ───────────────────────────────────────────

def create_access_token(user_id: int, username: str, permissions: list[str]) -> str:
    """签发 JWT Token"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "permissions": permissions,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """解析并验证 JWT Token，失败返回 None"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ─── 数据库查询 ───────────────────────────────────────────

async def get_user_with_roles(db: AsyncSession, user_id: int) -> Optional[User]:
    """通过 ID 查询用户及其所有角色（含 role 对象）"""
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[dict]:
    """
    验证用户名密码，成功后返回包含 token 和用户信息的 dict。
    失败返回 None。
    """
    # 1. 查用户
    stmt = (
        select(User)
        .where(User.username == username)
        .options(selectinload(User.roles))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None

    # 2. 校验密码
    if not verify_password(password, user.password_hash):
        return None

    # 3. 检查状态
    if user.status != "active":
        return None

    # 4. 收集所有权限
    permissions: set[str] = set()
    role_names: list[str] = []
    for role in user.roles:
        role_names.append(role.name)
        if role.permissions:
            permissions.update(role.permissions)

    # 5. 签发 Token
    token = create_access_token(user.id, user.username, sorted(permissions))

    # 6. 更新最后登录时间（naive datetime 匹配数据库 TIMESTAMP WITHOUT TIME ZONE）
    user.last_login = datetime.now()
    await db.commit()

    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role_names": role_names,
        "permissions": sorted(permissions),
        "access_token": token,
        "token_type": "bearer",
    }
