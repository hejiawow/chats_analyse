"""add quality review table

Revision ID: 20260608
Revises: c6e94026552d
Create Date: 2026-06-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260608'
down_revision = 'add_quality_guidance'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_exists = 'quality_review_results' in inspector.get_table_names()

    # 创建 quality_review_results 表（如不存在）
    if not table_exists:
        op.create_table(
            'quality_review_results',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('result_id', sa.Integer(), nullable=False, comment='关联质检结果ID'),
            sa.Column('secondary_risk_level', sa.String(16), nullable=False, comment='二次风险等级'),
            sa.Column('review_reason', sa.Text(), nullable=True, comment='二次判断理由'),
            sa.Column('suggested_action', sa.String(128), nullable=True, comment='建议处理动作'),
            sa.Column('confidence', sa.Float(), nullable=True, comment='AI置信度'),
            sa.Column('review_status', sa.String(16), nullable=False, server_default='pending', comment='审查状态'),
            sa.Column('review_mode', sa.String(16), nullable=True, comment='审查模式'),
            sa.Column('batch_id', sa.String(64), nullable=True, comment='批次号'),
            sa.Column('error_msg', sa.Text(), nullable=True, comment='失败原因'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('completed_at', sa.DateTime(), nullable=True, comment='完成时间'),
            sa.ForeignKeyConstraint(['result_id'], ['quality_check_results.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # 创建索引（如不存在）
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('quality_review_results')}
    if 'ix_quality_review_result_id' not in existing_indexes:
        op.create_index('ix_quality_review_result_id', 'quality_review_results', ['result_id'])
    if 'ix_quality_review_status' not in existing_indexes:
        op.create_index('ix_quality_review_status', 'quality_review_results', ['review_status'])
    if 'ix_quality_review_batch_id' not in existing_indexes:
        op.create_index('ix_quality_review_batch_id', 'quality_review_results', ['batch_id'])

    # 在 quality_check_results 表新增字段（如不存在）
    result_columns = {c['name'] for c in inspector.get_columns('quality_check_results')}
    if 'has_secondary_review' not in result_columns:
        op.add_column('quality_check_results',
            sa.Column('has_secondary_review', sa.Boolean(), nullable=True, default=False, comment='是否已进行二次审查')
        )

    # 设置默认值
    op.execute("UPDATE quality_check_results SET has_secondary_review = FALSE WHERE has_secondary_review IS NULL")


def downgrade():
    # 删除索引
    op.drop_index('ix_quality_review_batch_id', 'quality_review_results')
    op.drop_index('ix_quality_review_status', 'quality_review_results')
    op.drop_index('ix_quality_review_result_id', 'quality_review_results')

    # 删除表
    op.drop_table('quality_review_results')

    # 删除字段
    op.drop_column('quality_check_results', 'has_secondary_review')
