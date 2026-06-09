# -*- coding: utf-8 -*-
"""质检二次审查 — 共享查询条件（消除 API 层和 Task 层的重复）"""
from sqlalchemy import select, or_, and_
from app.models.result import QualityCheckResult, QualityReviewResult


def pending_review_conditions():
    """构造查询待二次审查记录的 SQLAlchemy where 条件列表。

    条件：has_secondary_review IS NOT TRUE 且有效风险等级为 high/medium，
    且不存在已 completed 的审查记录。

    用法：
        conditions = pending_review_conditions()
        stmt = select(QualityCheckResult.id).where(*conditions)
    """
    completed_subq = (
        select(QualityReviewResult.result_id)
        .where(QualityReviewResult.review_status == "completed")
        .scalar_subquery()
    )
    return [
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
        ),
        # 风险类别：投诉、退款、监管介入、取消订单
        QualityCheckResult.risk_category.in_(["投诉", "退款", "监管介入", "取消订单"]),
        # 处理状态：未处理
        QualityCheckResult.process_status == "pending",
    ]


def query_pending_review_ids(session, model_module=None):
    """查询所有待二次审查的质检结果 ID（同步版，供 Task 层使用）。

    Args:
        session: SQLAlchemy sync Session
    Returns:
        list[int]: 待审查的质检结果 ID 列表
    """
    conditions = pending_review_conditions()
    stmt = select(QualityCheckResult.id).where(*conditions)
    return [row[0] for row in session.execute(stmt).all()]
