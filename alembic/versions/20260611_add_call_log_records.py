"""add call_log_records table

Revision ID: 20260611_call_log
Revises: 20260609_retry_count
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260611_call_log'
down_revision = '20260611_perm'
branch_labels = None
depends_on = None


def upgrade():
    """创建 call_log_records 表"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_exists = 'call_log_records' in inspector.get_table_names()

    if not table_exists:
        op.create_table(
            'call_log_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('phone', sa.String(32), nullable=True, comment='手机号'),
            sa.Column('call_link', sa.Text(), nullable=True, comment='通话链接'),
            sa.Column('complaint_content', sa.Text(), nullable=True, comment='投诉内容'),
            sa.Column('request_time', sa.DateTime(), nullable=True, comment='接口请求时间'),
            sa.Column('synced_to_dingtalk', sa.Boolean(), server_default='false', nullable=True, comment='是否已同步到钉钉'),
            sa.Column('dingtalk_sync_error', sa.Text(), nullable=True, comment='钉钉同步失败原因'),
            sa.Column('raw_body', postgresql.JSONB(), nullable=True, comment='原始请求体（备用）'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.PrimaryKeyConstraint('id')
        )

        # 创建索引
        op.create_index('ix_call_log_phone', 'call_log_records', ['phone'])
        op.create_index('ix_call_log_created_at', 'call_log_records', ['created_at'])


def downgrade():
    """删除 call_log_records 表"""
    op.drop_index('ix_call_log_created_at', 'call_log_records')
    op.drop_index('ix_call_log_phone', 'call_log_records')
    op.drop_table('call_log_records')