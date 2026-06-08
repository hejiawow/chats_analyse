"""add review analysis fields to quality_review_results

Revision ID: 20260608_review_fields
Revises: 20260608_perm
Create Date: 2026-06-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260608_review_fields'
down_revision = '20260608_perm'
branch_labels = None
depends_on = None


def upgrade():
    """
    为 quality_review_results 表新增审查分析字段：
    - confirmed: 是否确认涉及退费或投诉
    - risk_type: 风险类型（退费/投诉/其他）
    - priority: 优先级（P0/P1/P2/P3）
    - first_mention_time: 客户首次提出退费或投诉的时间
    """
    conn = op.get_bind()

    # 幂等检查：只在列不存在时添加
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'quality_review_results'"
    ))
    existing_columns = {row[0] for row in result}

    if 'confirmed' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('confirmed', sa.Boolean(), nullable=True,
                      comment='是否确认涉及退费或投诉')
        )

    if 'risk_type' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('risk_type', sa.String(16), nullable=True,
                      comment='风险类型：退费/投诉/其他')
        )

    if 'priority' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('priority', sa.String(8), nullable=True,
                      comment='优先级：P0/P1/P2/P3')
        )

    if 'first_mention_time' not in existing_columns:
        op.add_column('quality_review_results',
            sa.Column('first_mention_time', sa.String(64), nullable=True,
                      comment='客户首次提出退费或投诉的时间')
        )

    # 创建索引
    op.create_index('ix_quality_review_risk_type', 'quality_review_results', ['risk_type'], unique=False)
    op.create_index('ix_quality_review_priority', 'quality_review_results', ['priority'], unique=False)


def downgrade():
    op.drop_index('ix_quality_review_priority', table_name='quality_review_results')
    op.drop_index('ix_quality_review_risk_type', table_name='quality_review_results')

    op.drop_column('quality_review_results', 'first_mention_time')
    op.drop_column('quality_review_results', 'priority')
    op.drop_column('quality_review_results', 'risk_type')
    op.drop_column('quality_review_results', 'confirmed')
