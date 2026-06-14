#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回填历史 quality_check_results 的 enrollment_phone / enrollment_phone_2

用法:
    python scripts/backfill_enrollment_phone.py
    python scripts/backfill_enrollment_phone.py --dry-run    # 仅预览，不写入
"""

import sys
import os
import argparse

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from app.services.phone_extractor import extract_enrollment_phones
from config import settings


def backfill(dry_run: bool = False, batch_size: int = 1000):
    db_url = settings.DATABASE_URL_SYNC
    if not db_url:
        print("错误: DATABASE_URL_SYNC 未配置，请检查 .env 文件")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # 查询所有 enrollment_phone 为空的记录
    cur.execute("""
        SELECT id, remark_phone, chat_title
        FROM quality_check_results
        WHERE enrollment_phone IS NULL
        ORDER BY id
    """)

    rows = cur.fetchall()
    total = len(rows)
    updated = 0
    skipped = 0

    if total == 0:
        print("无需回填：所有记录 enrollment_phone 已有值")
        cur.close()
        conn.close()
        return

    print(f"扫描到 {total} 条 enrollment_phone 为空的记录（dry_run={dry_run}）")

    for i, (row_id, remark_phone, chat_title) in enumerate(rows):
        result = extract_enrollment_phones(remark_phone, chat_title)
        ep = result["enrollment_phone"]
        ep2 = result["enrollment_phone_2"]

        if ep or ep2:
            if not dry_run:
                cur.execute("""
                    UPDATE quality_check_results
                    SET enrollment_phone = %s, enrollment_phone_2 = %s
                    WHERE id = %s
                """, (ep, ep2, row_id))
            updated += 1
        else:
            skipped += 1

        if (i + 1) % batch_size == 0:
            if not dry_run:
                conn.commit()
            print(f"  [{i+1}/{total}] 累计可更新: {updated}，无数据跳过: {skipped}")

    if not dry_run:
        conn.commit()

    cur.close()
    conn.close()

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}完成:")
    print(f"  扫描总数: {total}")
    print(f"  可更新:   {updated}")
    print(f"  无数据跳过: {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回填历史 enrollment_phone 数据")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际写入")
    parser.add_argument("--batch-size", type=int, default=1000, help="每批提交数量")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run, batch_size=args.batch_size)
