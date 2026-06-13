"""add chat time fields to quality_check_results

Revision ID: 20260613_03
Revises: 20260613_02
Create Date: 2026-06-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260613_03'
down_revision = '20260613_02'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 quality_check_results 表新增 chat_start_time 和 chat_end_time 字段，
    记录传给 LLM 分析的聊天记录时间范围，供二次审查复用起始时间。
    """
    conn = op.get_bind()

    # 幂等检查：只在列不存在时添加
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'quality_check_results'"
    ))
    existing_columns = {row[0] for row in result}

    if 'chat_start_time' not in existing_columns:
        op.add_column('quality_check_results',
            sa.Column('chat_start_time', sa.String(32), nullable=True,
                      comment='LLM分析聊天记录起始时间')
        )

    if 'chat_end_time' not in existing_columns:
        op.add_column('quality_check_results',
            sa.Column('chat_end_time', sa.String(32), nullable=True,
                      comment='LLM分析聊天记录结束时间')
        )


def downgrade():
    op.drop_column('quality_check_results', 'chat_end_time')
    op.drop_column('quality_check_results', 'chat_start_time')
