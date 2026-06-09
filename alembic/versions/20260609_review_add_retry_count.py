"""add retry_count to quality_review_results

Revision ID: 20260609_retry_count
Revises: 20260608_review_fields
Create Date: 2026-06-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260609_retry_count'
down_revision = '20260608_review_fields'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 quality_review_results 表新增 retry_count 字段，
    用于记录审查重试次数，防止无限重试。
    """
    conn = op.get_bind()

    # 幂等检查：只在列不存在时添加
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'quality_review_results'"
    ))
    existing_columns = {row[0] for row in result}

    if 'retry_count' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('retry_count', sa.Integer(), server_default='0',
                      comment='重试次数')
        )


def downgrade():
    op.drop_column('quality_review_results', 'retry_count')
