# -*- coding: utf-8 -*-
"""删除 case_extraction_results 表中的 11 个旧字段
运行方式：python -m app.scripts.drop_old_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.models.database import sync_engine

OLD_COLUMNS = [
    "scenario_type", "customer_type", "communication_stage", "sales_quote",
    "sales_ability_score", "sales_ability_desc",
    "replicability_score", "replicability_desc",
    "detail_score", "detail_desc", "comprehensive_review",
]


def main():
    print("=== 开始删除旧字段 ===")
    with sync_engine.connect() as conn:
        # 先查询现有列
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'case_extraction_results'
        """))
        existing = {row[0] for row in result}

        for col in OLD_COLUMNS:
            if col in existing:
                print(f"  删除: {col}")
                conn.execute(text(f"ALTER TABLE case_extraction_results DROP COLUMN {col}"))
            else:
                print(f"  跳过: {col}（已不存在）")

        conn.commit()
    print("=== 删除完成 ===")


if __name__ == "__main__":
    main()
