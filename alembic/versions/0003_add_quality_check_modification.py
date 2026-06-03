# -*- coding: utf-8 -*-
"""添加质检结果修改功能

为 quality_check_results 表新增备注和修正字段，
创建 quality_check_modification_logs 审计表。
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_quality_check_modification"
down_revision = "0002_add_trigger_party"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 为 quality_check_results 表添加修改相关字段
    op.add_column(
        "quality_check_results",
        sa.Column("remark", sa.Text, nullable=True, comment="质检备注"),
    )
    op.add_column(
        "quality_check_results",
        sa.Column("modified_risk_level", sa.String(16), nullable=True, comment="人工修正的风险等级"),
    )
    op.add_column(
        "quality_check_results",
        sa.Column("modified_at", sa.DateTime, nullable=True, comment="最后修改时间"),
    )
    op.add_column(
        "quality_check_results",
        sa.Column("modified_by", sa.String(64), nullable=True, comment="最后修改人ID"),
    )
    op.add_column(
        "quality_check_results",
        sa.Column("modified_by_name", sa.String(64), nullable=True, comment="最后修改人姓名"),
    )

    # 2. 创建审计日志表
    op.create_table(
        "quality_check_modification_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("result_id", sa.Integer, nullable=False, comment="质检结果ID"),
        sa.Column("user_id", sa.String(64), nullable=False, comment="修改人ID"),
        sa.Column("user_name", sa.String(64), nullable=True, comment="修改人姓名"),
        sa.Column("old_risk_level", sa.String(16), nullable=True, comment="原风险等级"),
        sa.Column("new_risk_level", sa.String(16), nullable=True, comment="新风险等级"),
        sa.Column("old_remark", sa.Text, nullable=True, comment="原备注"),
        sa.Column("new_remark", sa.Text, nullable=True, comment="新备注"),
        sa.Column("modified_at", sa.DateTime, nullable=False, comment="修改时间"),
    )

    # 3. 为审计表创建索引
    op.create_index(
        "ix_modification_log_result_id",
        "quality_check_modification_logs",
        ["result_id"],
    )
    op.create_index(
        "ix_modification_log_modified_at",
        "quality_check_modification_logs",
        ["modified_at"],
    )


def downgrade() -> None:
    # 1. 删除审计表索引
    op.drop_index("ix_modification_log_modified_at", table_name="quality_check_modification_logs")
    op.drop_index("ix_modification_log_result_id", table_name="quality_check_modification_logs")

    # 2. 删除审计表
    op.drop_table("quality_check_modification_logs")

    # 3. 删除 quality_check_results 表的新增字段
    op.drop_column("quality_check_results", "modified_by_name")
    op.drop_column("quality_check_results", "modified_by")
    op.drop_column("quality_check_results", "modified_at")
    op.drop_column("quality_check_results", "modified_risk_level")
    op.drop_column("quality_check_results", "remark")