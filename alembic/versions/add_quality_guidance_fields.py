"""add quality guidance fields

Revision ID: add_quality_guidance
Revises: drop_obsolete_result_cols
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "add_quality_guidance"
down_revision: Union[str, None] = "drop_obsolete_result_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    result_columns = {c["name"] for c in inspector.get_columns("quality_check_results")}
    columns_to_add = [
        ("issue_summary", sa.Column("issue_summary", sa.String(length=256), nullable=True, comment="一句话问题摘要")),
        ("action_priority", sa.Column("action_priority", sa.String(length=8), nullable=True, comment="处理优先级：P0/P1/P2/P3")),
        ("recommended_owner", sa.Column("recommended_owner", sa.String(length=32), nullable=True, comment="建议责任方")),
        ("action_type", sa.Column("action_type", sa.String(length=32), nullable=True, comment="建议动作类型")),
        ("follow_up_deadline", sa.Column("follow_up_deadline", sa.String(length=32), nullable=True, comment="建议处理时限")),
        ("needs_manual_review", sa.Column("needs_manual_review", sa.Boolean(), nullable=True, server_default=sa.false(), comment="是否需要人工复核")),
        ("confidence", sa.Column("confidence", sa.Float(), nullable=True, comment="AI置信度：0到1")),
        ("process_status", sa.Column("process_status", sa.String(length=32), nullable=True, server_default="pending", comment="处理状态")),
    ]
    for name, column in columns_to_add:
        if name not in result_columns:
            op.add_column("quality_check_results", column)

    if "risk_description" in result_columns:
        op.drop_column("quality_check_results", "risk_description")

    detail_columns = {c["name"] for c in inspector.get_columns("quality_check_details")}
    if "guidance" not in detail_columns:
        op.add_column(
            "quality_check_details",
            sa.Column("guidance", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="AI完整处理建议"),
        )
    if "suggested_action" in detail_columns:
        op.drop_column("quality_check_details", "suggested_action")

    result_indexes = {idx["name"] for idx in inspector.get_indexes("quality_check_results")}
    if "ix_quality_check_action_priority" not in result_indexes:
        op.create_index("ix_quality_check_action_priority", "quality_check_results", ["action_priority"], unique=False)
    if "ix_quality_check_process_status" not in result_indexes:
        op.create_index("ix_quality_check_process_status", "quality_check_results", ["process_status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    result_indexes = {idx["name"] for idx in inspector.get_indexes("quality_check_results")}
    if "ix_quality_check_process_status" in result_indexes:
        op.drop_index("ix_quality_check_process_status", table_name="quality_check_results")
    if "ix_quality_check_action_priority" in result_indexes:
        op.drop_index("ix_quality_check_action_priority", table_name="quality_check_results")

    result_columns = {c["name"] for c in inspector.get_columns("quality_check_results")}
    for name in [
        "process_status",
        "confidence",
        "needs_manual_review",
        "follow_up_deadline",
        "action_type",
        "recommended_owner",
        "action_priority",
        "issue_summary",
    ]:
        if name in result_columns:
            op.drop_column("quality_check_results", name)

    if "risk_description" not in result_columns:
        op.add_column("quality_check_results", sa.Column("risk_description", sa.Text(), nullable=True, comment="风险描述"))

    detail_columns = {c["name"] for c in inspector.get_columns("quality_check_details")}
    if "suggested_action" not in detail_columns:
        op.add_column("quality_check_details", sa.Column("suggested_action", sa.Text(), nullable=True, comment="建议处理措施"))
    if "guidance" in detail_columns:
        op.drop_column("quality_check_details", "guidance")
