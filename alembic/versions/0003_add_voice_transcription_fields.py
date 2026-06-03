# -*- coding: utf-8 -*-
"""添加语音转写字段到 quality_check_results 表

为质检结果表添加语音转写统计字段：
- voice_transcribed_count: 成功转写的语音消息数量
- voice_transcribe_error_count: 转写失败的语音消息数量

Revision ID: 0003_add_voice_transcription_fields
Revises: 0002_add_trigger_party
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_voice_transcription_fields"
down_revision = "0002_add_trigger_party"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 voice_transcribed_count 字段
    op.add_column(
        "quality_check_results",
        sa.Column(
            "voice_transcribed_count",
            sa.Integer,
            nullable=True,
            server_default="0",
            comment="成功转写的语音消息数量",
        ),
    )

    # 添加 voice_transcribe_error_count 字段
    op.add_column(
        "quality_check_results",
        sa.Column(
            "voice_transcribe_error_count",
            sa.Integer,
            nullable=True,
            server_default="0",
            comment="转写失败的语音消息数量",
        ),
    )


def downgrade() -> None:
    # 删除 voice_transcribe_error_count 字段
    op.drop_column("quality_check_results", "voice_transcribe_error_count")

    # 删除 voice_transcribed_count 字段
    op.drop_column("quality_check_results", "voice_transcribed_count")
