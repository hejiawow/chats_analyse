# -*- coding: utf-8 -*-
"""删除 case_script_library 表中的旧字段，只保留 embedding 相关核心字段
运行方式：python -m app.scripts.drop_library_old_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.models.database import sync_engine

# 删除评分字段（保留场景、引用、点评等字段）
OLD_COLUMNS = [
    "sales_ability_score", "sales_ability_desc",
    "replicability_score", "replicability_desc",
    "detail_score", "detail_desc",
]


def main():
    print("=== 开始删除 case_script_library 旧字段 ===")
    with sync_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'case_script_library'
        """))
        existing = {row[0] for row in result}

        for col in OLD_COLUMNS:
            if col in existing:
                print(f"  删除: {col}")
                conn.execute(text(f"ALTER TABLE case_script_library DROP COLUMN {col}"))
            else:
                print(f"  跳过: {col}（已不存在）")

        conn.commit()
    print("=== 删除完成 ===")


if __name__ == "__main__":
    main()
