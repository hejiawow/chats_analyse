"""split quality_check tables - move large fields to detail table

Revision ID: split_quality_tables
Revises: 0003_quality_mod
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'split_quality_tables'
down_revision: Union[str, None] = '0003_quality_mod'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """拆分质检表：创建详情表，迁移大字段数据，删除主表大字段列"""

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_exists = 'quality_check_details' in inspector.get_table_names()

    # 检查表结构是否完整（是否有 suggested_action 列）
    if table_exists:
        detail_columns = {c['name'] for c in inspector.get_columns('quality_check_details')}
        if 'suggested_action' not in detail_columns:
            # 表结构不完整，删除重建
            op.drop_table('quality_check_details')
            table_exists = False

    # 1. 创建详情表 quality_check_details（如不存在）
    if not table_exists:
        op.create_table(
            'quality_check_details',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('result_id', sa.Integer(), nullable=False, comment='关联质检结果ID'),
            sa.Column('keyword_matches', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='关键词匹配详情'),
            sa.Column('key_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='关键证据'),
            sa.Column('suggested_action', sa.Text(), nullable=True, comment='建议处理措施'),
            sa.Column('raw_response', sa.Text(), nullable=True, comment='AI原始响应'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('result_id'),
        )

    # 2. 创建索引（如果不存在）
    detail_indexes = {idx['name'] for idx in inspector.get_indexes('quality_check_details')}
    if 'ix_quality_check_detail_result_id' not in detail_indexes:
        op.create_index('ix_quality_check_detail_result_id', 'quality_check_details', ['result_id'], unique=False)

    # 3. 检查主表是否仍有大字段列（可能已被手动删除）
    result_columns = {c['name'] for c in inspector.get_columns('quality_check_results')}
    has_large_cols = 'keyword_matches' in result_columns

    if has_large_cols:
        # 迁移数据：从主表复制大字段到详情表（跳过已存在的记录）
        op.execute("""
            INSERT INTO quality_check_details (result_id, keyword_matches, key_evidence, suggested_action, raw_response, created_at)
            SELECT id, keyword_matches, key_evidence, suggested_action, raw_response, created_at
            FROM quality_check_results
            WHERE (keyword_matches IS NOT NULL
               OR key_evidence IS NOT NULL
               OR suggested_action IS NOT NULL
               OR raw_response IS NOT NULL)
            AND id NOT IN (SELECT result_id FROM quality_check_details)
        """)

        # 4. 删除主表的大字段列
        op.drop_column('quality_check_results', 'keyword_matches')
        op.drop_column('quality_check_results', 'key_evidence')
        op.drop_column('quality_check_results', 'suggested_action')
        op.drop_column('quality_check_results', 'raw_response')


def downgrade() -> None:
    """回滚：恢复主表大字段列，回迁数据，删除详情表"""

    # 1. 恢复主表的大字段列
    op.add_column('quality_check_results', sa.Column('keyword_matches', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='关键词匹配详情'))
    op.add_column('quality_check_results', sa.Column('key_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='关键证据'))
    op.add_column('quality_check_results', sa.Column('suggested_action', sa.Text(), nullable=True, comment='建议处理措施'))
    op.add_column('quality_check_results', sa.Column('raw_response', sa.Text(), nullable=True, comment='AI原始响应'))

    # 2. 回迁数据：从详情表复制回主表
    op.execute("""
        UPDATE quality_check_results q
        SET keyword_matches = d.keyword_matches,
            key_evidence = d.key_evidence,
            suggested_action = d.suggested_action,
            raw_response = d.raw_response
        FROM quality_check_details d
        WHERE q.id = d.result_id
    """)

    # 3. 删除索引
    op.drop_index('ix_quality_check_detail_result_id', table_name='quality_check_details')

    # 4. 删除详情表
    op.drop_table('quality_check_details')
