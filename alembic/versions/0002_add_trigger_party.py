# -*- coding: utf-8 -*-
"""添加 trigger_party 字段到 quality_check_results 表

为质检结果表新增 trigger_party 列，记录风险话题的触发方
（sales/customer/both/none），并添加索引。
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_trigger_party"
down_revision = "0001_initial_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quality_check_results",
        sa.Column("trigger_party", sa.String(16), nullable=True, comment="触发方：sales/customer/both"),
    )
    op.create_index(
        "ix_quality_check_trigger_party",
        "quality_check_results",
        ["trigger_party"],
    )


def downgrade() -> None:
    op.drop_index("ix_quality_check_trigger_party", table_name="quality_check_results")
    op.drop_column("quality_check_results", "trigger_party")
