"""add quality_review permissions to manager role

Revision ID: 20260608_perm
Revises: 20260608
Create Date: 2026-06-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260608_perm'
down_revision = '20260608'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 manager 角色添加二次审查权限：
    - read:quality_review - 查看二次审查结果
    - write:quality_review - 执行二次审查操作
    """
    # 使用 PostgreSQL 的 jsonb 操作添加新权限到 manager 角色
    # 只添加不存在的权限
    op.execute("""
        UPDATE roles
        SET permissions = permissions || '["read:quality_review", "write:quality_review"]'::jsonb
        WHERE name = 'manager'
        AND NOT permissions ? 'read:quality_review'
    """)


def downgrade():
    """
    从 manager 角色移除二次审查权限
    """
    op.execute("""
        UPDATE roles
        SET permissions = permissions - 'read:quality_review' - 'write:quality_review'
        WHERE name = 'manager'
    """)