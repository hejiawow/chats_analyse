# -*- coding: utf-8 -*-
"""Alembic 迁移环境配置"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 仅加载 .env 中的数据库 URL，不触发 app.models.database 的引擎创建
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL_SYNC", "")
if not db_url:
    # 尝试从 DATABASE_URL 转换同步 URL
    async_url = os.getenv("DATABASE_URL", "")
    if async_url:
        db_url = async_url.replace("+asyncpg", "+psycopg2", 1)

config = context.config

# 动态设置数据库 URL
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 延迟导入：仅在需要 autogenerate 时导入模型
# 手动迁移不需要 target_metadata
target_metadata = None


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
