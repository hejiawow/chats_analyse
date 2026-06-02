# -*- coding: utf-8 -*-
"""初始基线 — 标记当前数据库已有的表结构

此迁移不执行任何 DDL 操作，仅作为 Alembic 版本链的起点。
所有表已通过 Base.metadata.create_all() 创建。
"""

revision = "0001_initial_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
