"""add quality_check_tasks table and task_id FK

Revision ID: add_quality_tasks
Revises: split_quality_tables
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_quality_tasks'
down_revision: Union[str, None] = 'split_quality_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 检查表是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_exists = 'quality_check_tasks' in inspector.get_table_names()

    # 1. 创建质检任务表 quality_check_tasks（如不存在）
    if not table_exists:
        op.create_table(
            'quality_check_tasks',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('batch_task_id', sa.String(length=64), nullable=False, comment='批次号（UUID）'),
            sa.Column('status', sa.String(length=16), server_default='pending', comment='任务状态：pending/running/completed/cancelled/error/no_pairs/no_matches'),
            sa.Column('start_time', sa.String(length=32), nullable=True, comment='检测起始时间（用户选择的）'),
            sa.Column('end_time', sa.String(length=32), nullable=True, comment='检测结束时间（用户选择的）'),
            sa.Column('user_id_filter', sa.String(length=64), nullable=True, comment='销售ID筛选（可选）'),
            sa.Column('total_pairs', sa.Integer(), server_default='0', comment='待分析总条数'),
            sa.Column('completed_pairs', sa.Integer(), server_default='0', comment='已完成条数'),
            sa.Column('risk_detected', sa.Integer(), server_default='0', comment='检出风险条数'),
            sa.Column('no_chat_count', sa.Integer(), server_default='0', comment='无聊天记录条数'),
            sa.Column('failed_count', sa.Integer(), server_default='0', comment='分析失败条数'),
            sa.Column('cancelled_count', sa.Integer(), server_default='0', comment='被取消条数'),
            sa.Column('filtered_count', sa.Integer(), server_default='0', comment='被协议退费过滤条数'),
            sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息（API失败等）'),
            sa.Column('triggered_by', sa.String(length=64), nullable=True, comment='触发人（CLI/API/cron）'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='任务发起时间'),
            sa.Column('finished_at', sa.DateTime(), nullable=True, comment='任务结束时间'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('batch_task_id'),
        )

    # 2. 创建索引（如果不存在）
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('quality_check_tasks')}
    if 'ix_quality_check_task_batch_id' not in existing_indexes:
        op.create_index('ix_quality_check_task_batch_id', 'quality_check_tasks', ['batch_task_id'], unique=False)
    if 'ix_quality_check_task_status' not in existing_indexes:
        op.create_index('ix_quality_check_task_status', 'quality_check_tasks', ['status'], unique=False)
    if 'ix_quality_check_task_created' not in existing_indexes:
        op.create_index('ix_quality_check_task_created', 'quality_check_tasks', ['created_at'], unique=False)

    # 3. 给 quality_check_results 添加 task_id 外键列（nullable=True 兼容旧数据）
    result_columns = [c['name'] for c in inspector.get_columns('quality_check_results')]
    if 'task_id' not in result_columns:
        op.add_column(
            'quality_check_results',
            sa.Column('task_id', sa.Integer(), nullable=True, comment='关联质检任务ID'),
        )

    # 4. 创建外键约束（如果不存在）
    existing_fks = [fk['name'] for fk in inspector.get_foreign_keys('quality_check_results')]
    if 'fk_quality_check_result_task_id' not in existing_fks:
        op.create_foreign_key(
            'fk_quality_check_result_task_id',
            'quality_check_results',
            'quality_check_tasks',
            ['task_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 5. 创建 task_id 索引（如果不存在）
    result_indexes = {idx['name'] for idx in inspector.get_indexes('quality_check_results')}
    if 'ix_quality_check_task_id' not in result_indexes:
        op.create_index('ix_quality_check_task_id', 'quality_check_results', ['task_id'], unique=False)


def downgrade() -> None:
    # 1. 删除 quality_check_results 上的 task_id 索引和外键
    op.drop_index('ix_quality_check_task_id', table_name='quality_check_results')
    op.drop_constraint('fk_quality_check_result_task_id', 'quality_check_results', type_='foreignkey')
    op.drop_column('quality_check_results', 'task_id')

    # 2. 删除 quality_check_tasks 表
    op.drop_index('ix_quality_check_task_created', table_name='quality_check_tasks')
    op.drop_index('ix_quality_check_task_status', table_name='quality_check_tasks')
    op.drop_index('ix_quality_check_task_batch_id', table_name='quality_check_tasks')
    op.drop_table('quality_check_tasks')
