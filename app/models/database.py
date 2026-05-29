# -*- coding: utf-8 -*-
"""数据库连接"""
import os
import sys

# 强制使用 UTF-8 编码（解决 Windows 中文系统 psycopg2 编码问题）
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
if sys.platform == 'win32':
    os.environ['PGCLIENTENCODING'] = 'UTF8'

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings

# 异步引擎（FastAPI 用）
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)

# 同步引擎（Alembic 迁移 / Celery 用）
# 添加 connect_args 指定 client_encoding 解决 Windows 编码问题
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC, 
    echo=False,
    connect_args={'client_encoding': 'utf8'}
)

class Base(DeclarativeBase):
    pass


def init_db():
    """创建所有表（仅开发/初始化用）"""
    # 尝试创建 pgvector 扩展（如果已安装）
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    except Exception:
        pass  # pgvector 未安装，使用 JSONB 方案
    Base.metadata.create_all(bind=sync_engine)
