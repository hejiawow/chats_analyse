# -*- coding: utf-8 -*-
"""质检二次审查批量任务"""

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import QualityCheckResult, QualityReviewResult, QualityCheckDetail
from app.agents.quality_review import quality_review_agent
from app.services.hujing_api import get_chat_records_for_quality_check
from config import now_shanghai, to_naive_shanghai


@shared_task(bind=True, name="batch_quality_review")
def batch_quality_review_task(self, result_ids: list, batch_id: str):
    """批量二次审查任务

    Args:
        result_ids: 质检结果ID列表
        batch_id: 批次号（UUID）

    流程：
    1. 逐条处理质检结果
    2. 调用二次审查Agent
    3. 保存结果
    4. 更新质检结果标记
    """
    with Session(sync_engine) as session:
        for result_id in result_ids:
            try:
                # 查询质检结果
                stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
                quality_result = session.execute(stmt).scalar_one_or_none()

                if not quality_result:
                    print(f"质检结果 {result_id} 不存在，跳过")
                    continue

                # 检查是否已审查
                if quality_result.has_secondary_review:
                    print(f"质检结果 {result_id} 已审查，跳过")
                    continue

                # 查询详情
                detail_stmt = select(QualityCheckDetail).where(
                    QualityCheckDetail.result_id == result_id
                )
                detail = session.execute(detail_stmt).scalar_one_or_none()
                key_evidence = detail.key_evidence if detail else []

                # 获取聊天记录
                chat_records = get_chat_records_for_quality_check(
                    user_id=quality_result.user_id,
                    friend_id=quality_result.friend_id,
                    end_time="2099-12-31 23:59:59",
                )

                # 调用二次审查Agent
                review_result = quality_review_agent(
                    result_id=result_id,
                    chat_records=chat_records,
                    key_evidence=key_evidence,
                    issue_summary=quality_result.issue_summary or "",
                    initial_risk_level=quality_result.modified_risk_level or quality_result.risk_level,
                    raw_response=detail.raw_response if detail else "",
                )

                # 保存审查结果
                review_record = QualityReviewResult(
                    result_id=result_id,
                    confirmed=review_result.get("confirmed"),
                    risk_type=review_result.get("risk_type"),
                    priority=review_result.get("priority"),
                    first_mention_time=review_result.get("first_mention_time"),
                    secondary_risk_level=review_result.get("secondary_risk_level"),
                    review_reason=review_result.get("review_reason"),
                    suggested_action=review_result.get("suggested_action"),
                    confidence=review_result.get("confidence"),
                    review_status="completed" if review_result.get("status") == "success" else "failed",
                    review_mode="batch",
                    batch_id=batch_id,
                    error_msg=review_result.get("error_msg"),
                    created_at=to_naive_shanghai(now_shanghai()),
                    completed_at=to_naive_shanghai(now_shanghai()) if review_result.get("status") == "success" else None,
                )
                session.add(review_record)

                # 更新质检结果标记
                quality_result.has_secondary_review = True

                session.commit()
                print(f"质检结果 {result_id} 二次审查完成")

            except Exception as e:
                print(f"质检结果 {result_id} 二次审查失败: {str(e)}")
                # 记录失败状态
                review_record = QualityReviewResult(
                    result_id=result_id,
                    confirmed=None,
                    risk_type="其他",
                    priority="P2",
                    first_mention_time=None,
                    secondary_risk_level="unknown",
                    review_reason=f"审查失败: {str(e)}",
                    suggested_action="主管复核",
                    confidence=0.0,
                    review_status="failed",
                    review_mode="batch",
                    batch_id=batch_id,
                    error_msg=str(e),
                    created_at=to_naive_shanghai(now_shanghai()),
                )
                session.add(review_record)
                session.commit()

        return {"batch_id": batch_id, "total": len(result_ids)}