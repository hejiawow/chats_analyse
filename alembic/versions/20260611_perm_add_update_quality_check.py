"""add update:quality_check permission to manager role

Revision ID: 20260611_perm
Revises: 20260609_retry_count
Create Date: 2026-06-11

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260611_perm'
down_revision = '20260609_retry_count'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 manager 角色补充人工处理权限：
    - update:quality_check - 修改处理状态、备注、风险等级
    """
    op.execute("""
        UPDATE roles
        SET permissions = permissions || '["update:quality_check"]'::jsonb
        WHERE name = 'manager'
        AND NOT permissions ? 'update:quality_check'
    """)


def downgrade():
    """
    从 manager 角色移除人工处理权限
    """
    op.execute("""
        UPDATE roles
        SET permissions = permissions - 'update:quality_check'
        WHERE name = 'manager'
    """)
