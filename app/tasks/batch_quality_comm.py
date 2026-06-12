# -*- coding: utf-8 -*-
"""云客数据源批量质检任务 — 独立于虎鲸的 Celery 并发处理流程"""
import json
import logging
from datetime import datetime, timedelta
from celery import chord
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.services.communication_api import get_sales_friends, get_chat_records_for_quality_check
from app.agents.quality_check import quality_check_agent
from app.models.database import sync_engine
from app.models.result import QualityCheckResult, QualityCheckDetail, QualityCheckTask
from config import settings, now_shanghai
from app.api.quality_check_query import invalidate_quality_check_stats_cache
from app.services.cache import cache_clear_pattern
from app.services.log_service import log as _log

from app.tasks.batch_quality import (
    update_batch_progress,
    increment_batch_progress,
    get_batch_progress,
    is_batch_cancelled,
    clear_batch_cancel,
)

logger = logging.getLogger(__name__)


def _update_task_status(batch_task_id: str, **kwargs):
    """更新数据库中的批量任务状态"""
    with Session(sync_engine) as session:
        from sqlalchemy import update
        stmt = (
            update(QualityCheckTask)
            .where(QualityCheckTask.batch_task_id == batch_task_id)
            .values(**kwargs)
        )
        session.execute(stmt)
        session.commit()


@celery_app.task(bind=True, name="app.tasks.batch_quality_comm.run_single_check_comm", rate_limit="20/m")
def run_single_check_comm(self, batch_task_id: str, db_task_id: int,
                          sales_user_id: str, customer_wechat_no: str,
                          start_time: str, end_time: str,
                          friend_info: dict = None):
    """云客数据源子任务：对单个销售-客户对进行质检分析"""
    if is_batch_cancelled(batch_task_id):
        _log(batch_task_id, f"[取消] 销售:{sales_user_id} 客户:{customer_wechat_no} 任务已取消", "info")
        return {
            "status": "cancelled",
            "sales_user_id": sales_user_id,
            "customer_wechat_no": customer_wechat_no,
            "keyword_detected": "no",
        }

    _log(batch_task_id, f"[开始] 销售:{sales_user_id} 客户:{customer_wechat_no} 开始分析", "info")

    try:
        # 云客数据源：使用与查询销售好友列表相同的时间范围查询沟通记录
        # 即前端传入的 start_time 和 end_time
        actual_start_time = start_time
        actual_end_time = end_time

        # 获取聊天记录（已转换格式）
        _log(batch_task_id, f"[获取] 销售:{sales_user_id} 客户:{customer_wechat_no} 正在获取聊天记录，时间范围={actual_start_time} ~ {actual_end_time}", "info")
        chat_records = get_chat_records_for_quality_check(
            sales_user_id=sales_user_id,
            customer_wechat_no=customer_wechat_no,
            end_time_str=actual_end_time,
            start_time_str=actual_start_time,
        )

        if not chat_records:
            _log(batch_task_id, f"[无数据] 销售:{sales_user_id} 客户:{customer_wechat_no} 无聊天记录", "info")
            increment_batch_progress(batch_task_id)
            return {
                "status": "no_chat",
                "sales_user_id": sales_user_id,
                "customer_wechat_no": customer_wechat_no,
                "keyword_detected": "no",
            }

        _log(
            batch_task_id,
            f"[分析] 销售:{sales_user_id} 客户:{customer_wechat_no} 获取到 {len(chat_records)} 条记录，开始质检...",
            "info",
        )

        # 执行质检分析（复用现有 Agent）
        result = quality_check_agent(
            sales_user_id, None, chat_records,  # friend_id 传 None（云客数据源无整型ID）
            start_time=actual_start_time,
            end_time=actual_end_time,
        )

        # 只有检测到关键词才保存到数据库
        if result.get("keyword_detected") == "yes":
            _log(
                batch_task_id,
                f"[风险] 销售:{sales_user_id} 客户:{customer_wechat_no} "
                f"检测到风险关键词，保存结果",
                "info",
            )

            # 从 friend_info 中提取辅助信息
            user_name = ""
            friend_wx_id = ""
            friend_nick = ""
            if friend_info:
                user_name = friend_info.get("salesName", "")
                friend_wx_id = friend_info.get("friendWechatId", "")
                friend_nick = friend_info.get("friendWechatNo", "")

            # 将 keyword_matches (list of dicts) 转换为逗号分隔的字符串
            keyword_matches_list = result.get("keyword_matches", [])
            if keyword_matches_list and isinstance(keyword_matches_list, list):
                detected_keywords_str = ", ".join([
                    m.get("keyword", "") for m in keyword_matches_list if m.get("keyword")
                ])
            else:
                detected_keywords_str = None

            with Session(sync_engine) as session:
                record = QualityCheckResult(
                    user_id=sales_user_id,
                    user_name=user_name,
                    friend_id=None,  # 云客数据源无整型 friend_id
                    friend_wx_id=friend_wx_id,
                    friend_nick=friend_nick,
                    customer_wechat_no=customer_wechat_no,
                    datasource="communication",
                    trigger_party=result.get("trigger_party", "unknown"),
                    risk_level=result.get("risk_level", "medium"),
                    risk_category=result.get("risk_category", ""),
                    keyword_detected="yes",
                    detected_keywords=detected_keywords_str,  # 存储关键词名称（逗号分隔）
                    issue_summary=result.get("issue_summary", ""),
                    action_priority=result.get("action_priority", ""),
                    recommended_owner=result.get("recommended_owner", ""),
                    action_type=result.get("action_type", ""),
                    follow_up_deadline=result.get("follow_up_deadline"),
                    needs_manual_review=result.get("needs_manual_review", False),
                    confidence=result.get("confidence"),
                    task_id=db_task_id,
                    created_at=now_shanghai(),
                )
                session.add(record)
                session.flush()

                # 保存详情表
                detail = QualityCheckDetail(
                    result_id=record.id,
                    guidance=result.get("guidance"),  # JSONB 存储AI处理建议（风险原因、客户诉求、建议话术、培训建议等）
                    keyword_matches=keyword_matches_list,  # JSONB 存储完整关键词匹配详情
                    key_evidence=result.get("key_evidence"),  # JSONB 存储关键证据
                    raw_response=result.get("raw_response"),  # Text 存储原始响应
                    created_at=now_shanghai(),
                )
                session.add(detail)
                session.commit()
        else:
            _log(
                batch_task_id,
                f"[安全] 销售:{sales_user_id} 客户:{customer_wechat_no} 未检测到风险关键词",
                "info",
            )

        increment_batch_progress(batch_task_id)
        return {
            "status": "completed",
            "sales_user_id": sales_user_id,
            "customer_wechat_no": customer_wechat_no,
            "keyword_detected": result.get("keyword_detected", "no"),
        }

    except Exception as e:
        logger.exception(f"[comm质检] 子任务异常: {sales_user_id}/{customer_wechat_no}")
        _log(batch_task_id, f"[错误] 销售:{sales_user_id} 客户:{customer_wechat_no} 分析失败: {str(e)}", "error")
        increment_batch_progress(batch_task_id)
        return {
            "status": "failed",
            "sales_user_id": sales_user_id,
            "customer_wechat_no": customer_wechat_no,
            "error": str(e),
        }


@celery_app.task(bind=True, name="app.tasks.batch_quality_comm.on_batch_complete_comm")
def on_batch_complete_comm(self, results, batch_task_id: str):
    """云客批量质检完成回调"""
    risk_count = sum(1 for r in results if r.get("keyword_detected") == "yes")
    no_chat_count = sum(1 for r in results if r.get("status") == "no_chat")
    failed_count = sum(1 for r in results if r.get("status") == "failed")
    cancelled_count = sum(1 for r in results if r.get("status") == "cancelled")

    # 确定最终状态
    if cancelled_count == len(results):
        final_status = "cancelled"
    elif failed_count > 0 and risk_count == 0 and no_chat_count == 0:
        final_status = "error"
    else:
        final_status = "completed"

    _log(
        batch_task_id,
        f"[完成] 批量质检完成: 总计 {len(results)} 对, "
        f"风险 {risk_count}, 无聊天 {no_chat_count}, 失败 {failed_count}, 取消 {cancelled_count}",
        "info",
    )

    update_batch_progress(
        batch_task_id,
        completed=len(results),
        total=len(results),
        status=final_status,
        risk_detected=risk_count,
        no_chat=no_chat_count,
        failed=failed_count,
        cancelled=cancelled_count,
    )

    # 更新数据库任务记录
    _update_task_status(
        batch_task_id,
        status=final_status,
        completed_pairs=len(results),
        risk_detected=risk_count,
        no_chat_count=no_chat_count,
        failed_count=failed_count,
        cancelled_count=cancelled_count,
        finished_at=now_shanghai(),
    )

    clear_batch_cancel(batch_task_id)

    # 清除统计缓存
    invalidate_quality_check_stats_cache()
    cache_clear_pattern("quality_check:stats:user:*")

    _log(batch_task_id, f"[完成] 批量质检完成: 总计 {len(results)} 对, 风险 {risk_count}, 无聊天 {no_chat_count}, 失败 {failed_count}", "info")

    return {
        "status": final_status,
        "total_pairs": len(results),
        "risk_detected": risk_count,
        "no_chat": no_chat_count,
        "failed": failed_count,
        "cancelled": cancelled_count,
    }


@celery_app.task(bind=True, name="app.tasks.batch_quality_comm.run_batch_quality_comm")
def run_batch_quality_comm(self, batch_task_id: str, start_time: str, end_time: str,
                           user_id_filter: str = None, limit: int = 500):
    """云客数据源批量质检主任务

    流程：
    1. 调用 sales-friends 接口获取所有销售-客户对
    2. 可选按 user_id 筛选
    3. 对每个客户对获取聊天记录，进行关键词预过滤
    4. 分发子任务 run_single_check_comm
    """
    _log(batch_task_id, f"[启动] 云客批量质检任务开始，时间范围: {start_time} ~ {end_time}", "info")
    if user_id_filter:
        _log(batch_task_id, f"[筛选] 指定销售ID: {user_id_filter}", "info")

    try:
        # 1. 创建质检任务记录
        with Session(sync_engine) as session:
            task = QualityCheckTask(
                batch_task_id=batch_task_id,
                datasource="communication",
                start_time=start_time,
                end_time=end_time,
                status="running",
                created_at=now_shanghai(),
            )
            session.add(task)
            session.commit()
            db_task_id = task.id

        # 2. 获取销售-好友对
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_ts = int(end_dt.timestamp())
        start_ts = int(start_dt.timestamp())

        _log(batch_task_id, f"[获取] 正在获取销售-客户对...", "info")
        all_friends = get_sales_friends(
            start_time=start_ts,
            end_time=end_ts,
            org_level=0,
            org_id=0,
        )

        if not all_friends:
            _log(batch_task_id, "[无数据] 时间范围内无销售-客户对", "info")
            update_batch_progress(batch_task_id, 0, 0, "no_pairs")
            _update_task_status(batch_task_id, status="no_pairs", finished_at=now_shanghai())
            return {"status": "no_pairs", "message": "时间范围内无销售-客户对"}

        _log(batch_task_id, f"[成功] 获取到 {len(all_friends)} 个销售-客户对", "info")

        # 3. 可选按 user_id 筛选
        if user_id_filter:
            all_friends = [f for f in all_friends if f.get("salesUserId") == user_id_filter]

        # 4. 构建 (salesUserId, customerWechatNo) 去重列表，并保留 friend_info 索引
        pairs_set = set()
        friend_info_index = {}
        for item in all_friends:
            sales_user_id = item.get("salesUserId")
            friend_wechat_id = item.get("friendWechatId")
            friend_wechat_no = item.get("friendWechatNo")
            # 优先使用 friendWechatNo（客户微信号标识）
            customer_id = friend_wechat_no or friend_wechat_id
            if sales_user_id and customer_id:
                pair_key = (sales_user_id, customer_id)
                if pair_key not in pairs_set:
                    pairs_set.add(pair_key)
                    friend_info_index[customer_id] = item

        matched_pairs = list(pairs_set)

        # 5. 关键词预过滤（可选：获取聊天记录并做关键词匹配，仅保留匹配的对话）
        # 为了减少 API 调用，此处先不做预过滤，直接分发所有对（与虎鲸的 messages 方式不同）

        if not matched_pairs:
            _log(batch_task_id, "[完成] 无待分析的销售-客户对", "info")
            update_batch_progress(batch_task_id, 0, 0, "no_matches")
            _update_task_status(batch_task_id, status="no_matches", finished_at=now_shanghai())
            return {"status": "no_matches", "message": "无待分析的销售-客户对"}

        # 6. 限制数量
        matched_pairs = matched_pairs[:limit]

        _log(batch_task_id, f"[分发] 开始分发 {len(matched_pairs)} 个子任务...", "info")

        # 7. 初始化进度
        update_batch_progress(batch_task_id, 0, len(matched_pairs), "running")
        _update_task_status(batch_task_id, total_pairs=len(matched_pairs))

        # 8. 创建子任务列表
        subtasks = [
            run_single_check_comm.s(
                batch_task_id,
                db_task_id,
                pair[0],  # sales_user_id
                pair[1],  # customer_wechat_no
                start_time,
                end_time,
                friend_info_index.get(pair[1]),  # friend_info（复用）
            )
            for pair in matched_pairs
        ]

        # 9. 使用 chord：子任务完成后触发回调
        callback = on_batch_complete_comm.s(batch_task_id)
        chord(subtasks)(callback)

        return {
            "status": "started",
            "total_pairs": len(matched_pairs),
            "message": f"分发 {len(matched_pairs)} 个云客质检子任务",
        }

    except Exception as e:
        logger.exception(f"[comm批量质检] 主任务异常: {e}")
        _log(batch_task_id, f"[错误] 批量质检主任务异常: {str(e)}", "error")
        update_batch_progress(batch_task_id, 0, 0, "error", error=str(e))
        _update_task_status(batch_task_id, status="error", finished_at=now_shanghai())
        return {"status": "error", "message": str(e)}


def get_comm_batch_progress(batch_task_id: str) -> dict:
    """获取云客批量任务进度"""
    return get_batch_progress(batch_task_id)


def cancel_comm_batch_task(batch_task_id: str) -> bool:
    """取消云客批量质检任务"""
    from app.tasks.batch_quality import cancel_batch_task
    return cancel_batch_task(batch_task_id)
