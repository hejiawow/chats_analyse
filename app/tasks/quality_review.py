# -*- coding: utf-8 -*-
"""质检二次审查批量任务"""
import uuid
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import select, update, or_, and_
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import QualityCheckResult, QualityReviewResult, QualityCheckDetail, QualityCheckTask
from app.agents.quality_review import quality_review_agent
from app.services.hujing_api import get_chat_records_for_quality_check
from app.services.communication_api import get_chat_records_for_quality_check as get_comm_chat_records
from app.services.quality_review_query import pending_review_conditions, query_pending_review_ids
from config import now_shanghai, to_naive_shanghai, settings

# Task层最大重试次数，超过后标记为已审查不再重试
MAX_TASK_RETRIES = 10


def _upsert_failed_record(result_id: int, error_msg: str, batch_id: str):
    """在独立事务中安全地写入/更新失败记录，避免主 Session 状态污染"""
    try:
        with Session(sync_engine) as err_session:
            qr = err_session.execute(
                select(QualityCheckResult).where(QualityCheckResult.id == result_id)
            ).scalar_one_or_none()
            if not qr:
                return

            existing_failed = err_session.execute(
                select(QualityReviewResult).where(
                    QualityReviewResult.result_id == result_id,
                    QualityReviewResult.review_status == "failed"
                )
            ).scalar_one_or_none()

            if existing_failed:
                existing_failed.retry_count = (existing_failed.retry_count or 0) + 1
                existing_failed.error_msg = error_msg
                existing_failed.batch_id = batch_id
                existing_failed.review_reason = f"审查异常: {error_msg}"
                retry_count = existing_failed.retry_count
            else:
                err_session.add(QualityReviewResult(
                    result_id=result_id,
                    confirmed=None,
                    risk_type="其他",
                    priority="P2",
                    first_mention_time=None,
                    secondary_risk_level="unknown",
                    review_reason=f"审查异常: {error_msg}",
                    suggested_action="主管复核",
                    confidence=0.0,
                    review_status="failed",
                    review_mode="batch",
                    batch_id=batch_id,
                    error_msg=error_msg,
                    retry_count=1,
                    created_at=to_naive_shanghai(now_shanghai()),
                ))
                retry_count = 1

            if retry_count >= MAX_TASK_RETRIES:
                qr.has_secondary_review = True

            err_session.commit()
    except Exception as inner_e:
        print(f"[batch_review] result_id={result_id} 异常处理也失败: {inner_e}")


def _process_single_review(session: Session, result_id: int, batch_id: str, idx: int, total: int) -> str:
    """处理单条二次审查，返回 'success' / 'failed' / 'skip'"""

    # 查询质检结果
    stmt = select(QualityCheckResult).where(QualityCheckResult.id == result_id)
    quality_result = session.execute(stmt).scalar_one_or_none()

    if not quality_result:
        print(f"[batch_review] [{idx}/{total}] result_id={result_id} 不存在，跳过")
        return "skip"

    # === 原子占位：先占位后处理，防止多 Worker 并发重复调 AI ===
    # 关键：这是整个函数的第一道防线，必须在任何检查之前执行
    # UPDATE ... WHERE id=? AND has_secondary_review IS NOT TRUE
    # rowcount==1 表示抢占成功，rowcount==0 表示已被其他 Worker 抢占
    claim_result = session.execute(
        update(QualityCheckResult)
        .where(
            QualityCheckResult.id == result_id,
            or_(
                QualityCheckResult.has_secondary_review == False,
                QualityCheckResult.has_secondary_review == None,
            )
        )
        .values(has_secondary_review=True)
    )
    session.commit()

    if claim_result.rowcount == 0:
        print(f"[batch_review] [{idx}/{total}] result_id={result_id} 已被其他Worker抢占，跳过")
        return "skip"

    print(f"[batch_review] [{idx}/{total}] result_id={result_id} 占位成功，开始处理")

    # === 占位成功后，检查是否已有 completed 记录（防止重复写入）===
    # 这一步必须在 claim 之后执行，确保只有一个 Worker 能走到这里
    existing_completed = session.execute(
        select(QualityReviewResult).where(
            QualityReviewResult.result_id == result_id,
            QualityReviewResult.review_status == "completed"
        )
    ).scalar_one_or_none()
    if existing_completed:
        print(f"[batch_review] [{idx}/{total}] result_id={result_id} 已有completed审查记录，释放占位并跳过")
        # 释放占位，让其他 Worker 可以重试（如果有 failed 记录的话）
        quality_result.has_secondary_review = False
        session.commit()
        return "skip"

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

    # 获取聊天记录（根据数据源使用不同 API）
    now_str = to_naive_shanghai(now_shanghai()).strftime("%Y-%m-%d %H:%M:%S")
    is_comm = quality_result.datasource == "communication"
    print(f"[batch_review] [{idx}/{total}] result_id={result_id} 数据源={quality_result.datasource}, "
          f"是云客={is_comm}")

    if is_comm:
        # 云客数据源：使用 customer_wechat_no，需要获取任务时间范围
        task_start_time = None
        task_end_time = None
        if quality_result.task_id:
            task = session.execute(
                select(QualityCheckTask).where(QualityCheckTask.id == quality_result.task_id)
            ).scalar_one_or_none()
            if task:
                task_start_time = task.start_time
                task_end_time = task.end_time

        end_time_str = task_end_time or now_str
        start_time_str = task_start_time
        if not start_time_str:
            # 兜底：往前推配置天数
            end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
            start_time_str = (end_dt - timedelta(days=settings.QUALITY_CHECK_CHAT_DAYS)).strftime("%Y-%m-%d %H:%M:%S")

        print(f"[batch_review] [{idx}/{total}] result_id={result_id} 获取云客聊天记录 "
              f"(salesUserId={quality_result.user_id}, customerWechatNo={quality_result.customer_wechat_no}, "
              f"时间={start_time_str} ~ {end_time_str})...")
        chat_records = get_comm_chat_records(
            sales_user_id=quality_result.user_id,
            customer_wechat_no=quality_result.customer_wechat_no or "",
            end_time_str=end_time_str,
            start_time_str=start_time_str,
        )
    else:
        # 虎鲸数据源：使用 friend_id
        print(f"[batch_review] [{idx}/{total}] result_id={result_id} 获取虎鲸聊天记录 (end_time={now_str})...")
        chat_records = get_chat_records_for_quality_check(
            user_id=quality_result.user_id,
            friend_id=quality_result.friend_id,
            end_time=now_str,
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
            existing_failed.review_mode = "batch"
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

        # 占位已在处理前设置，无需重复设置
        session.commit()
        print(f"[batch_review] [{idx}/{total}] result_id={result_id} 审查完成并保存 ✓")
        return "success"

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
            # 达到最大重试：保持占位 True，永久标记为已审查
            session.commit()
            print(f"[batch_review] [{idx}/{total}] result_id={result_id} "
                  f"已达最大重试({MAX_TASK_RETRIES}次)，标记为已审查")
        else:
            # 未达最大重试：释放占位，让下次定时任务能重新抢到
            quality_result.has_secondary_review = False
            session.commit()
            print(f"[batch_review] [{idx}/{total}] result_id={result_id} "
                  f"审查失败(第{retry_count}/{MAX_TASK_RETRIES}次)，释放占位等待下次自动重试")
        return "failed"


@shared_task(bind=True, name="batch_quality_review", time_limit=3600, soft_time_limit=3500)
def batch_quality_review_task(self, result_ids: list, batch_id: str):
    """批量二次审查任务（并行处理）

    Args:
        result_ids: 质检结果ID列表
        batch_id: 批次号（UUID）

    流程：
    1. 并行处理质检结果（线程池，并发数=AI_MAX_CONCURRENT）
    2. 每条独立 Session + 原子占位，防并发冲突
    3. AI 调用受信号量控制，不会超限
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from config import settings

    total = len(result_ids)
    success_count = 0
    fail_count = 0
    skip_count = 0

    print(f"[batch_review] ========== 批量二次审查开始 batch_id={batch_id} 共 {total} 条 ==========")

    # 并发数：取 AI_MAX_CONCURRENT 和任务数的较小值
    max_workers = min(settings.AI_MAX_CONCURRENT, total)
    print(f"[batch_review] 并发数: {max_workers}")

    def process_one(idx: int, result_id: int) -> str:
        """处理单条，独立 Session"""
        with Session(sync_engine) as session:
            try:
                result = _process_single_review(session, result_id, batch_id, idx, total)
                return result
            except Exception as e:
                error_msg = str(e)
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} 意外异常: {error_msg}")

                # 回滚当前 session
                try:
                    session.rollback()
                except Exception:
                    pass

                # 用独立事务记录失败
                _upsert_failed_record(result_id, error_msg, batch_id)
                return "failed"

    # 线程池并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_one, idx, rid): (idx, rid)
            for idx, rid in enumerate(result_ids, 1)
        }

        for future in as_completed(futures):
            idx, result_id = futures[future]
            try:
                result = future.result()
                if result == "success":
                    success_count += 1
                elif result == "failed":
                    fail_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                print(f"[batch_review] [{idx}/{total}] result_id={result_id} future异常: {e}")
                fail_count += 1

    summary = (f"[batch_review] ========== 批量二次审查完成 batch_id={batch_id} "
               f"总计={total} 成功={success_count} 失败={fail_count} 跳过={skip_count} ==========")
    print(summary)
    return {"batch_id": batch_id, "total": total, "success": success_count, "failed": fail_count, "skipped": skip_count}


@shared_task(bind=True, name="auto_quality_review_consumer")
def auto_quality_review_consumer(self):
    """单次执行：查询待审查数据，有则处理，无则退出

    由 Celery Beat 每5分钟触发一次。
    替代了之前的 while True 消费者模式，避免 Worker 进程泄漏。
    """
    print("[auto_review] 定时任务触发，查询未审查的高中风险结果...")

    with Session(sync_engine) as session:
        result_ids = query_pending_review_ids(session)

    if not result_ids:
        print("[auto_review] 暂无未审查的高中风险结果，跳过")
        return {"batch_id": None, "total": 0, "message": "无待审查结果"}

    batch_id = str(uuid.uuid4())
    print(f"[auto_review] 发现 {len(result_ids)} 条未审查结果，提交 batch_quality_review_task 到队列")

    # 异步提交到 Celery 队列，避免并发执行多个批次
    batch_quality_review_task.delay(result_ids, batch_id)
    return {"batch_id": batch_id, "total": len(result_ids), "message": "已提交到队列"}
