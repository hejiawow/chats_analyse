# -*- coding: utf-8 -*-
"""诊断二次审查状态"""
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import Session
from app.models.database import sync_engine
from app.models.result import QualityCheckResult, QualityReviewResult

with Session(sync_engine) as session:
    # 1. 统计各风险等级的质检结果数量
    print("=== 1. 质检结果风险等级分布 ===")
    risk_counts = session.execute(
        select(
            QualityCheckResult.risk_level,
            QualityCheckResult.modified_risk_level,
            func.count()
        ).group_by(
            QualityCheckResult.risk_level,
            QualityCheckResult.modified_risk_level
        )
    ).all()
    for r in risk_counts:
        print(f"  risk_level={r[0]:<8} modified={r[1] or '-':<8} count={r[2]}")

    # 2. 统计 has_secondary_review 状态
    print("\n=== 2. has_secondary_review 状态分布 ===")
    review_flag_counts = session.execute(
        select(
            QualityCheckResult.has_secondary_review,
            func.count()
        ).group_by(QualityCheckResult.has_secondary_review)
    ).all()
    for r in review_flag_counts:
        print(f"  has_secondary_review={r[0]} count={r[1]}")

    # 3. 查询待审查的 ID（与任务逻辑一致）
    print("\n=== 3. 待二次审查的结果 ===")
    completed_subq = (
        select(QualityReviewResult.result_id)
        .where(QualityReviewResult.review_status == "completed")
        .scalar_subquery()
    )
    stmt = select(
        QualityCheckResult.id,
        QualityCheckResult.risk_level,
        QualityCheckResult.modified_risk_level,
        QualityCheckResult.has_secondary_review,
        QualityCheckResult.user_name,
        QualityCheckResult.issue_summary,
    ).where(
        or_(
            QualityCheckResult.has_secondary_review == False,
            QualityCheckResult.has_secondary_review == None,
        ),
        QualityCheckResult.id.not_in(completed_subq),
        or_(
            QualityCheckResult.modified_risk_level.in_(["high", "medium"]),
            and_(
                QualityCheckResult.modified_risk_level == None,
                QualityCheckResult.risk_level.in_(["high", "medium"])
            )
        )
    )
    pending = session.execute(stmt).all()
    print(f"  待审查数量: {len(pending)}")
    for r in pending[:10]:
        print(f"  id={r[0]:<5} risk={r[1]:<8} modified={r[2] or '-':<8} flag={r[3]} user={r[4]} summary={(r[5] or '-')[:40]}")
    if len(pending) > 10:
        print(f"  ... 还有 {len(pending) - 10} 条")

    # 4. 已有审查记录
    print("\n=== 4. 已完成的二次审查记录 ===")
    completed = session.execute(
        select(
            QualityReviewResult.result_id,
            QualityReviewResult.review_status,
            QualityReviewResult.secondary_risk_level,
            QualityReviewResult.review_mode,
        )
    ).all()
    print(f"  已完成审查数量: {len(completed)}")
    for r in completed[:5]:
        print(f"  result_id={r[0]} status={r[1]} level={r[2]} mode={r[3]}")
