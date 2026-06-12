"""add datasource field to quality check tables

Revision ID: 20260610_datasource
Revises: 20260609_retry_count
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260610_datasource'
down_revision: Union[str, None] = '20260611_call_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    # 1. quality_check_results: add datasource column
    existing_cols = [c["name"] for c in inspector.get_columns("quality_check_results")]
    if "datasource" not in existing_cols:
        op.add_column(
            "quality_check_results",
            sa.Column(
                "datasource",
                sa.String(50),
                nullable=True,
                server_default="hujing",
                comment="数据来源: hujing / communication",
            ),
        )

    # 2. quality_check_results: add customer_wechat_no column
    if "customer_wechat_no" not in existing_cols:
        op.add_column(
            "quality_check_results",
            sa.Column(
                "customer_wechat_no",
                sa.String(100),
                nullable=True,
                comment="客户微信号/企微标识（云客数据源）",
            ),
        )

    # 3. quality_check_results: make friend_id nullable
    # (was NOT NULL, now nullable for 云客 data source)
    friend_col_info = next(
        (c for c in inspector.get_columns("quality_check_results") if c["name"] == "friend_id"),
        None,
    )
    if friend_col_info and not friend_col_info.get("nullable", True):
        op.alter_column(
            "quality_check_results",
            "friend_id",
            existing_type=sa.BigInteger(),
            nullable=True,
            comment="好友ID（虎鲸数据源有值，云客数据源可为空）",
        )

    # 4. quality_check_tasks: add datasource column
    task_cols = [c["name"] for c in inspector.get_columns("quality_check_tasks")]
    if "datasource" not in task_cols:
        op.add_column(
            "quality_check_tasks",
            sa.Column(
                "datasource",
                sa.String(50),
                nullable=True,
                server_default="hujing",
                comment="数据来源: hujing / communication",
            ),
        )


def downgrade() -> None:
    op.drop_column("quality_check_tasks", "datasource")
    op.alter_column(
        "quality_check_results",
        "friend_id",
        existing_type=sa.BigInteger(),
        nullable=False,
        comment="好友ID",
    )
    op.drop_column("quality_check_results", "customer_wechat_no")
    op.drop_column("quality_check_results", "datasource")
