# -*- coding: utf-8 -*-
"""初始化 RBAC 用户和角色数据

用法: python scripts/init_auth.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy.orm import Session
from app.models.database import sync_engine, init_db
from app.models.auth import User, Role, UserRole
from app.services.auth import hash_password


def init_roles_and_users():
    """创建默认角色和初始用户"""
    init_db()

    with Session(sync_engine) as session:
        # 清理旧数据
        session.query(UserRole).delete()
        session.query(User).delete()
        session.query(Role).delete()
        session.commit()

        # 创建角色
        roles_data = [
            ("admin", "系统管理员，拥有所有权限", ["admin:all"]),
            ("manager", "主管，可查看和触发分析", [
                "read:dashboard", "read:referral", "read:cases",
                "read:journey", "read:followup", "read:scriptlib", "read:rag",
                "read:quality_check", "write:quality_check",
                "write:trigger",
            ]),
            ("sales", "销售，仅可查看自己的数据和触发分析", [
                "read:dashboard", "read:cases", "read:scriptlib", "write:trigger",
            ]),
        ]

        created_roles = {}
        for name, desc, perms in roles_data:
            role = Role(name=name, description=desc, permissions=perms, created_at=datetime.now())
            session.add(role)
            session.flush()
            created_roles[name] = role
            print(f"  [OK] 创建角色: {name}")

        # 创建用户
        users_data = [
            ("admin", "admin123", "admin@ahujiaoyu.com", "admin"),
            ("manager", "manager123", "", "manager"),
        ]

        for username, password, email, role_name in users_data:
            user = User(
                username=username,
                password_hash=hash_password(password),
                email=email or None,
                status="active",
                created_at=datetime.now(),
            )
            session.add(user)
            session.flush()
            session.add(UserRole(user_id=user.id, role_id=created_roles[role_name].id))
            print(f"  [OK] 创建用户: {username} (密码: {password}) -> 角色: {role_name}")

        session.commit()
        print("\n初始化完成！")
        print("  管理员账号: admin / admin123")
        print("  主管账号: manager / manager123")


if __name__ == "__main__":
    init_roles_and_users()
