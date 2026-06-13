"""add review correction fields to quality_review_results

Revision ID: 20260613_01
Revises: 20260611_call_log
Create Date: 2026-06-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260613_01'
down_revision = '20260611_call_log'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 quality_review_results 表新增 initial_risk_level_corrected 和
    initial_deviation_type 字段，记录二次审查对初次分析的修正情况。
    """
    conn = op.get_bind()

    # 幂等检查：只在列不存在时添加
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'quality_review_results'"
    ))
    existing_columns = {row[0] for row in result}

    if 'initial_risk_level_corrected' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('initial_risk_level_corrected', sa.Boolean(), nullable=True,
                      comment='是否修正了初次风险等级')
        )

    if 'initial_deviation_type' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('initial_deviation_type', sa.String(64), nullable=True,
                      comment='初次分析偏差类型')
        )


def downgrade():
    op.drop_column('quality_review_results', 'initial_deviation_type')
    op.drop_column('quality_review_results', 'initial_risk_level_corrected')
