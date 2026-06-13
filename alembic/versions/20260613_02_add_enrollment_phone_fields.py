"""add enrollment phone fields to quality_check_results

Revision ID: 20260613_02
Revises: 20260613_01
Create Date: 2026-06-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260613_02'
down_revision = '20260613_01'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 quality_check_results 表新增 enrollment_phone 和 enrollment_phone_2 字段，
    用于存储从备注手机号和好友备注中提取的客户报班手机号。
    """
    conn = op.get_bind()

    # 幂等检查：只在列不存在时添加
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'quality_check_results'"
    ))
    existing_columns = {row[0] for row in result}

    if 'enrollment_phone' not in existing_columns:
        op.add_column('quality_check_results',
            sa.Column('enrollment_phone', sa.String(32), nullable=True,
                      comment='报班手机号')
        )

    if 'enrollment_phone_2' not in existing_columns:
        op.add_column('quality_check_results',
            sa.Column('enrollment_phone_2', sa.String(32), nullable=True,
                      comment='第二报班手机号')
        )


def downgrade():
    op.drop_column('quality_check_results', 'enrollment_phone_2')
    op.drop_column('quality_check_results', 'enrollment_phone')
