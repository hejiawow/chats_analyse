# -*- coding: utf-8 -*-
"""认证相关 ORM 模型：users、roles、user_roles"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.database import Base


class User(Base):
    """系统用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, comment="用户名")
    password_hash = Column(String(256), nullable=False, comment="密码哈希")
    email = Column(String(128), comment="邮箱")
    phone = Column(String(32), comment="手机号")
    status = Column(String(16), default="active", comment="active / disabled")
    last_login = Column(DateTime, comment="最后登录时间")
    created_at = Column(DateTime, comment="创建时间")

    roles = relationship("Role", secondary="user_roles", backref="users")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "status": self.status,
            "role_names": [r.name for r in self.roles],
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Role(Base):
    """系统角色表"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, comment="角色名称")
    description = Column(String(256), comment="角色描述")
    permissions = Column(JSONB, comment="权限列表 JSON")
    created_at = Column(DateTime, comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions or [],
        }


class UserRole(Base):
    """用户-角色关联表"""
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
