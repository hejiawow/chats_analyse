# -*- coding: utf-8 -*-
"""为 case_extraction_results 表添加 customer_profile 字段
运行方式：python -m app.scripts.add_customer_profile
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.models.database import sync_engine


def main():
    print("=== 开始添加 customer_profile 字段 ===")
    with sync_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'case_extraction_results'
            AND column_name = 'customer_profile'
        """))
        if result.fetchone():
            print("  已存在，跳过")
        else:
            print("  添加: customer_profile")
            conn.execute(text(
                "ALTER TABLE case_extraction_results ADD COLUMN customer_profile TEXT"
            ))
        conn.commit()
    print("=== 添加完成 ===")


if __name__ == "__main__":
    main()
