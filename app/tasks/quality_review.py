# -*- coding: utf-8 -*-
"""质检二次审查批量任务"""
import uuid

from celery import shared_task
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import QualityCheckResult, QualityReviewResult, QualityCheckDetail, QualityCheckTask
from app.agents.quality_review import quality_review_agent
from app.services.hujing_api import get_chat_records_for_quality_check
from config import now_shanghai, to_naive_shanghai

# Task层最大重试次数，超过后标记为已审查不再重试
MAX_TASK_RETRIES = 10


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
    total = len(result_ids)
    success_count = 0
    fail_count = 0
    skip_count = 0
    print(f"[batch_review] ========== 批量二次审查开始 batch_id={batch_id} 共 {total} 条 ==========")

    with Session(sync_engine) as session:
        for idx, result_id in enumerate(result_ids, 1):
            try:
                print(f"[batch_review] [{idx}/{total}] 开始处理 result_id={result_id}")

                # 查询质检结果
                stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
                quality_result = session.execute(stmt).scalar_one_or_none()

                if not quality_result:
                    print(f"[batch_review] [{idx}/{total}] result_id={result_id} 不存在，跳过")
                    skip_count += 1
                    continue

                # 检查是否已审查
                if quality_result.has_secondary_review:
                    print(f"[batch_review] [{idx}/{total}] result_id={result_id} 已审查，跳过")
                    skip_count += 1
                    continue

                # 查询详情
                detail_stmt = select(QualityCheckDetail).where(
                    QualityCheckDetail.result_id == result_id
                )
                detail = session.execute(detail_stmt).scalar_one_or_none()
                key_evidence = detail.key_evidence if detail else []
                has_raw_response = bool(detail and detail.raw_response)
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} 详情加载完成: "
                      f"关键证据={len(key_evidence)}条, raw_response={'有' if has_raw_response else '无'}, "
                      f"user={quality_result.user_id}, friend={quality_result.friend_id}")

                # 获取聊天记录（从任务表查询真实检测时间）
                task_end_time = "2099-12-31 23:59:59"
                if quality_result.task_id:
                    task_stmt = select(QualityCheckTask).where(QualityCheckTask.id == quality_result.task_id)
                    task = session.execute(task_stmt).scalar_one_or_none()
                    if task and task.end_time:
                        task_end_time = task.end_time
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} 获取聊天记录 (end_time={task_end_time})...")
                chat_records = get_chat_records_for_quality_check(
                    user_id=quality_result.user_id,
                    friend_id=quality_result.friend_id,
                    end_time=task_end_time,
                )
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} 获取到 {len(chat_records)} 条聊天记录")

                # 调用二次审查Agent
                effective_risk = quality_result.modified_risk_level or quality_result.risk_level
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} 调用AI审查Agent (风险等级={effective_risk})...")
                review_result = quality_review_agent(
                    result_id=result_id,
                    chat_records=chat_records,
                    key_evidence=key_evidence,
                    issue_summary=quality_result.issue_summary or "",
                    initial_risk_level=effective_risk,
                    raw_response=detail.raw_response if detail else "",
                )
                ai_status = review_result.get("status", "unknown")
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} AI审查返回: status={ai_status}, "
                      f"confirmed={review_result.get('confirmed')}, risk_type={review_result.get('risk_type')}, "
                      f"priority={review_result.get('priority')}")

                # 查找已有的失败记录（用于重试时更新而非重复创建）
                existing_failed = session.execute(
                    select(QualityReviewResult).where(
                        QualityReviewResult.result_id == result_id,
                        QualityReviewResult.review_status == "failed"
                    )
                ).scalar_one_or_none()

                if ai_status == "success":
                    # 成功：更新已有失败记录或创建新记录
                    if existing_failed:
                        existing_failed.confirmed = review_result.get("confirmed")
                        existing_failed.risk_type = review_result.get("risk_type")
                        existing_failed.priority = review_result.get("priority")
                        existing_failed.first_mention_time = review_result.get("first_mention_time")
                        existing_failed.secondary_risk_level = review_result.get("secondary_risk_level")
                        existing_failed.review_reason = review_result.get("review_reason")
                        existing_failed.suggested_action = review_result.get("suggested_action")
                        existing_failed.confidence = review_result.get("confidence")
                        existing_failed.review_status = "completed"
                        existing_failed.error_msg = None
                        existing_failed.completed_at = to_naive_shanghai(now_shanghai())
                        existing_failed.batch_id = batch_id
                    else:
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
                            review_status="completed",
                            review_mode="batch",
                            batch_id=batch_id,
                            error_msg=None,
                            retry_count=0,
                            created_at=to_naive_shanghai(now_shanghai()),
                            completed_at=to_naive_shanghai(now_shanghai()),
                        )
                        session.add(review_record)

                    quality_result.has_secondary_review = True
                    session.commit()
                    success_count += 1
                    print(f"[batch_review] [{idx}/{total}] result_id={result_id} 审查完成并保存 ✓")

                else:
                    # 失败：更新已有记录或创建新记录
                    if existing_failed:
                        new_retry = (existing_failed.retry_count or 0) + 1
                        existing_failed.retry_count = new_retry
                        existing_failed.review_reason = review_result.get("review_reason")
                        existing_failed.error_msg = review_result.get("error_msg")
                        existing_failed.batch_id = batch_id
                        retry_count = new_retry
                    else:
                        review_record = QualityReviewResult(
                            result_id=result_id,
                            confirmed=None,
                            risk_type="其他",
                            priority="P2",
                            first_mention_time=None,
                            secondary_risk_level="unknown",
                            review_reason=review_result.get("review_reason", "AI审查失败"),
                            suggested_action="主管复核",
                            confidence=0.0,
                            review_status="failed",
                            review_mode="batch",
                            batch_id=batch_id,
                            error_msg=review_result.get("error_msg"),
                            retry_count=1,
                            created_at=to_naive_shanghai(now_shanghai()),
                        )
                        session.add(review_record)
                        retry_count = 1

                    if retry_count >= MAX_TASK_RETRIES:
                        quality_result.has_secondary_review = True
                        session.commit()
                        fail_count += 1
                        print(f"[batch_review] [{idx}/{total}] result_id={result_id} "
                              f"已达最大重试({MAX_TASK_RETRIES}次)，标记为已审查")
                    else:
                        session.commit()
                        fail_count += 1
                        print(f"[batch_review] [{idx}/{total}] result_id={result_id} "
                              f"审查失败(第{retry_count}/{MAX_TASK_RETRIES}次)，等待下次自动重试")

            except Exception as e:
                # 意外异常（非AI调用失败，如数据库错误等）
                fail_count += 1
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} 意外异常: {str(e)}")

                existing_failed = session.execute(
                    select(QualityReviewResult).where(
                        QualityReviewResult.result_id == result_id,
                        QualityReviewResult.review_status == "failed"
                    )
                ).scalar_one_or_none()

                if existing_failed:
                    new_retry = (existing_failed.retry_count or 0) + 1
                    existing_failed.retry_count = new_retry
                    existing_failed.review_reason = f"审查异常: {str(e)}"
                    existing_failed.error_msg = str(e)
                    existing_failed.batch_id = batch_id
                    retry_count = new_retry
                else:
                    review_record = QualityReviewResult(
                        result_id=result_id,
                        confirmed=None,
                        risk_type="其他",
                        priority="P2",
                        first_mention_time=None,
                        secondary_risk_level="unknown",
                        review_reason=f"审查异常: {str(e)}",
                        suggested_action="主管复核",
                        confidence=0.0,
                        review_status="failed",
                        review_mode="batch",
                        batch_id=batch_id,
                        error_msg=str(e),
                        retry_count=1,
                        created_at=to_naive_shanghai(now_shanghai()),
                    )
                    session.add(review_record)
                    retry_count = 1

                if retry_count >= MAX_TASK_RETRIES:
                    quality_result.has_secondary_review = True
                session.commit()

    summary = (f"[batch_review] ========== 批量二次审查完成 batch_id={batch_id} "
               f"总计={total} 成功={success_count} 失败={fail_count} 跳过={skip_count} ==========")
    print(summary)
    return {"batch_id": batch_id, "total": total, "success": success_count, "failed": fail_count, "skipped": skip_count}


@shared_task(bind=True, name="auto_quality_review")
def auto_quality_review_task(self):
    """定时自动审查所有未审查的高中风险结果

    由 Celery Beat 每2小时触发一次。
    查询条件：has_secondary_review=False 且有效风险等级为 high/medium。
    有效风险等级判定：modified_risk_level 优先，无修正时用 risk_level。
    """
    print("[auto_quality_review] 定时任务触发，查询未审查的高中风险结果...")

    with Session(sync_engine) as session:
        stmt = select(QualityCheckResult.id).where(
            QualityCheckResult.has_secondary_review == False,
            or_(
                QualityCheckResult.modified_risk_level.in_(["high", "medium"]),
                and_(
                    QualityCheckResult.modified_risk_level == None,
                    QualityCheckResult.risk_level.in_(["high", "medium"])
                )
            )
        )
        result_ids = [row[0] for row in session.execute(stmt).all()]

    if not result_ids:
        print("[auto_quality_review] 暂无未审查的高中风险结果，跳过")
        return {"batch_id": None, "total": 0, "message": "无待审查结果"}

    batch_id = str(uuid.uuid4())
    print(f"[auto_quality_review] 发现 {len(result_ids)} 条未审查结果，委托 batch_quality_review_task 执行")

    # 直接复用 batch_quality_review_task 的核心逻辑（同步调用，不嵌套 Celery 任务）
    return batch_quality_review_task(result_ids, batch_id)