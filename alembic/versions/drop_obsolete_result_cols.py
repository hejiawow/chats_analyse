"""drop obsolete columns from quality_check_results

Revision ID: drop_obsolete_result_cols
Revises: add_quality_tasks
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'drop_obsolete_result_cols'
down_revision: Union[str, None] = 'add_quality_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 quality_check_results 上已废弃的三列：
    - check_time_start（时间范围已移至 quality_check_tasks）
    - check_time_end（时间范围已移至 quality_check_tasks）
    - batch_task_id（已改用 task_id 外键关联任务表）
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('quality_check_results')}

    if 'check_time_start' in existing_columns:
        op.drop_column('quality_check_results', 'check_time_start')
    if 'check_time_end' in existing_columns:
        op.drop_column('quality_check_results', 'check_time_end')
    if 'batch_task_id' in existing_columns:
        op.drop_column('quality_check_results', 'batch_task_id')


def downgrade() -> None:
    op.add_column(
        'quality_check_results',
        sa.Column('batch_task_id', sa.String(length=64), nullable=True,
                  comment='批量任务ID（批次号，兼容旧数据）'),
    )
    op.add_column(
        'quality_check_results',
        sa.Column('check_time_end', sa.String(length=32), nullable=True,
                  comment='检测结束时间'),
    )
    op.add_column(
        'quality_check_results',
        sa.Column('check_time_start', sa.String(length=32), nullable=True,
                  comment='检测起始时间'),
    )
