# -*- coding: utf-8 -*-
"""重置二次审查数据 — 将已审核记录恢复为未审核状态

用法：
    python scripts/reset_review_data.py              # 预览模式（仅统计，不修改）
    python scripts/reset_review_data.py --execute    # 执行重置
    python scripts/reset_review_data.py --execute --keep-records  # 重置标记但保留审查记录

场景：
    1. 开发/测试环境需要反复触发二次审查流程
    2. 修复代码后需要用真实数据重新验证
"""
import sys
import argparse
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import QualityCheckResult, QualityReviewResult


def show_stats(session: Session):
    """显示当前二次审查相关数据统计"""

    # 1. quality_check_results 中 has_secondary_review 分布
    print("=== 1. 质检结果 has_secondary_review 分布 ===")
    rows = session.execute(
        select(QualityCheckResult.has_secondary_review, func.count())
        .group_by(QualityCheckResult.has_secondary_review)
    ).all()
    for flag, count in rows:
        label = {True: "已审核(True)", False: "未审核(False)", None: "空(NULL)"}
        print(f"  {label.get(flag, flag)}: {count} 条")

    # 2. quality_review_results 中审查状态分布
    print("\n=== 2. 二次审查记录 review_status 分布 ===")
    rows = session.execute(
        select(QualityReviewResult.review_status, func.count())
        .group_by(QualityReviewResult.review_status)
    ).all()
    if not rows:
        print("  (无记录)")
    for status, count in rows:
        print(f"  {status}: {count} 条")

    # 3. 审查模式分布
    print("\n=== 3. 审查模式 review_mode 分布 ===")
    rows = session.execute(
        select(QualityReviewResult.review_mode, func.count())
        .group_by(QualityReviewResult.review_mode)
    ).all()
    if not rows:
        print("  (无记录)")
    for mode, count in rows:
        print(f"  {mode}: {count} 条")

    # 4. 可被重新审查的高中风险记录数（重置后会被选中的）
    print("\n=== 4. 高中风险质检结果统计 ===")
    high_medium_count = session.execute(
        select(func.count()).select_from(QualityCheckResult).where(
            or_(
                QualityCheckResult.modified_risk_level.in_(["high", "medium"]),
                and_(
                    QualityCheckResult.modified_risk_level == None,
                    QualityCheckResult.risk_level.in_(["high", "medium"])
                )
            )
        )
    ).scalar()
    print(f"  高中风险总数: {high_medium_count} 条")
    print(f"  (重置后这些都会被纳入待审查)")

    # 5. Redis 锁状态
    print("\n=== 5. Redis 锁状态 ===")
    try:
        from app.services.cache import get_redis
        redis_client = get_redis()
        if redis_client:
            lock_val = redis_client.get("quality_review:auto_batch_lock")
            if lock_val:
                ttl = redis_client.ttl("quality_review:auto_batch_lock")
                print(f"  锁状态: 已锁定 (TTL={ttl}秒)")
            else:
                print("  锁状态: 未锁定 ✓")
        else:
            print("  Redis 不可用（跳过）")
    except Exception as e:
        print(f"  Redis 检查失败: {e}")


def reset_data(session: Session, keep_records: bool = False):
    """重置二次审查数据

    Args:
        session: 数据库 Session
        keep_records: True=仅重置标记（保留审查记录）; False=删除审查记录+重置标记
    """
    # Step 1: 重置 has_secondary_review 标记
    updated = session.execute(
        QualityCheckResult.__table__.update()
        .where(
            or_(
                QualityCheckResult.has_secondary_review == True,
            )
        )
        .values(has_secondary_review=False)
    )
    print(f"\n✓ 已重置 {updated.rowcount} 条质检结果的 has_secondary_review → False")

    # Step 2: 处理审查记录
    if keep_records:
        # 保留记录但标记为 archived（不影响查询逻辑）
        updated = session.execute(
            QualityReviewResult.__table__.update()
            .where(QualityReviewResult.review_status.in_(["completed", "failed"]))
            .values(review_status="archived")
        )
        print(f"✓ 已将 {updated.rowcount} 条审查记录标记为 archived（保留数据）")
    else:
        # 删除所有审查记录
        deleted = session.execute(
            QualityReviewResult.__table__.delete()
        )
        print(f"✓ 已删除 {deleted.rowcount} 条审查记录")

    # Step 3: 清除 Redis 锁
    try:
        from app.services.cache import get_redis
        redis_client = get_redis()
        if redis_client:
            deleted_lock = redis_client.delete("quality_review:auto_batch_lock")
            if deleted_lock:
                print("✓ 已清除 Redis 分布式锁")
    except Exception:
        pass

    session.commit()
    print("\n✅ 重置完成！可以重新触发二次审查了。")


def main():
    parser = argparse.ArgumentParser(description="重置二次审查数据")
    parser.add_argument("--execute", action="store_true", help="执行重置（默认仅预览）")
    parser.add_argument("--keep-records", action="store_true",
                        help="保留审查记录（仅重置标记，记录改为 archived）")
    args = parser.parse_args()

    with Session(sync_engine) as session:
        print("=" * 50)
        print("  质检二次审查数据 — 当前状态")
        print("=" * 50)
        show_stats(session)

        if not args.execute:
            print("\n" + "=" * 50)
            print("  当前为预览模式，未做任何修改")
            print("  加 --execute 参数执行重置")
            print("  加 --keep-records 保留审查记录")
            print("=" * 50)
            return

        print("\n" + "=" * 50)
        print("  执行重置...")
        print("=" * 50)
        reset_data(session, keep_records=args.keep_records)

        print("\n" + "=" * 50)
        print("  重置后状态")
        print("=" * 50)
        show_stats(session)


if __name__ == "__main__":
    main()
