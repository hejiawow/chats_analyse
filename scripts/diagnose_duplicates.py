# -*- coding: utf-8 -*-
"""诊断二次审查重复数据"""
from sqlalchemy import text
from app.models.database import sync_engine
from sqlalchemy.orm import Session

with Session(sync_engine) as session:
    print("=" * 80)
    print("二次审查重复数据诊断")
    print("=" * 80)

    # 1. 检查哪些 result_id 有多条 completed 审查记录
    print("\n=== 1. 重复的审查记录（同一 result_id 有多条 completed）===")
    result = session.execute(text("""
        SELECT
          result_id,
          COUNT(*) as review_count,
          ARRAY_AGG(id ORDER BY created_at) as review_ids,
          ARRAY_AGG(review_mode ORDER BY created_at) as modes,
          ARRAY_AGG(batch_id ORDER BY created_at) as batch_ids,
          MIN(created_at) as first_created,
          MAX(created_at) as last_created
        FROM quality_review_results
        WHERE review_status = 'completed'
        GROUP BY result_id
        HAVING COUNT(*) > 1
        ORDER BY review_count DESC
        LIMIT 20
    """))
    duplicates = result.fetchall()

    if not duplicates:
        print("  ✓ 没有发现重复记录")
    else:
        print(f"  ✗ 发现 {len(duplicates)} 个 result_id 有重复审查记录：")
        for row in duplicates:
            result_id, count, ids, modes, batches, first, last = row
            time_diff = (last - first).total_seconds() if first and last else 0
            print(f"\n  result_id={result_id}")
            print(f"    重复次数: {count}")
            print(f"    审查记录ID: {ids}")
            print(f"    审查模式: {modes}")
            print(f"    批次号: {batches}")
            print(f"    时间跨度: {time_diff:.1f}秒 (首次: {first}, 末次: {last})")

            # 判断重复原因
            unique_batches = len(set([b for b in batches if b]))
            if unique_batches > 1:
                print(f"    ⚠️  原因: 多个不同批次 ({unique_batches}个)")
            elif 'instant' in modes:
                print(f"    ⚠️  原因: 包含即时审查（可能并发请求）")
            elif time_diff < 5:
                print(f"    ⚠️  原因: 时间间隔极短（可能竞态条件）")
            else:
                print(f"    ⚠️  原因: 未知（需人工排查）")

    # 2. 统计总体情况
    print("\n=== 2. 总体统计 ===")
    result = session.execute(text("""
        SELECT
          COUNT(*) as total_reviews,
          COUNT(DISTINCT result_id) as unique_results,
          COUNT(*) - COUNT(DISTINCT result_id) as duplicate_count
        FROM quality_review_results
        WHERE review_status = 'completed'
    """))
    row = result.fetchone()
    total, unique, dups = row
    print(f"  总审查记录数: {total}")
    print(f"  唯一 result_id 数: {unique}")
    print(f"  重复记录数: {dups} ({dups*100.0/total:.1f}%)" if total > 0 else "  无数据")

    # 3. 按批次统计
    print("\n=== 3. 按批次统计 ===")
    result = session.execute(text("""
        SELECT
          batch_id,
          COUNT(*) as total,
          COUNT(DISTINCT result_id) as unique_results,
          COUNT(*) - COUNT(DISTINCT result_id) as duplicates,
          MIN(created_at) as started
        FROM quality_review_results
        WHERE review_status = 'completed' AND batch_id IS NOT NULL
        GROUP BY batch_id
        ORDER BY started DESC
        LIMIT 10
    """))
    batches = result.fetchall()
    if batches:
        print(f"  最近 {len(batches)} 个批次：")
        for row in batches:
            batch_id, total, unique, dups, started = row
            short_id = batch_id[:8] if batch_id else "instant"
            dup_mark = " ⚠️有重复" if dups > 0 else ""
            print(f"    {short_id}... | 总数:{total} 唯一:{unique} 重复:{dups}{dup_mark} | {started}")

    # 4. 检查 instant 模式的重复
    print("\n=== 4. Instant 模式重复分析 ===")
    result = session.execute(text("""
        SELECT
          result_id,
          COUNT(*) as count,
          ARRAY_AGG(id ORDER BY created_at) as ids,
          MIN(created_at) as first_time,
          MAX(created_at) as last_time
        FROM quality_review_results
        WHERE review_status = 'completed' AND review_mode = 'instant'
        GROUP BY result_id
        HAVING COUNT(*) > 1
    """))
    instant_dups = result.fetchall()
    if not instant_dups:
        print("  ✓ instant 模式没有重复")
    else:
        print(f"  ✗ instant 模式有 {len(instant_dups)} 个重复：")
        for row in instant_dups:
            result_id, count, ids, first, last = row
            time_diff = (last - first).total_seconds() if first and last else 0
            print(f"    result_id={result_id}: {count}次, IDs={ids}, 间隔={time_diff:.1f}秒")

    # 5. 建议的清理 SQL
    if duplicates:
        print("\n=== 5. 建议的清理 SQL ===")
        print("  保留每个 result_id 最早的一条，删除重复的：")
        print("""
  DELETE FROM quality_review_results
  WHERE review_status = 'completed'
    AND id NOT IN (
      SELECT DISTINCT ON (result_id) id
      FROM quality_review_results
      WHERE review_status = 'completed'
      ORDER BY result_id, created_at ASC, id ASC
    );
        """)
        print("  ⚠️  执行前请先备份！")

    print("\n" + "=" * 80)
