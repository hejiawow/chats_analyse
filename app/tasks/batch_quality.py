# -*- coding: utf-8 -*-
"""批量质检任务 — Celery并发处理（使用 chat/pairs API）"""
import json
from datetime import datetime, timedelta
from celery import chord
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.services.hujing_api import get_chat_pairs, get_chat_records, get_all_chat_messages, get_all_sales, get_friends_list
from app.agents.quality_check import quality_check_agent
from app.models.database import sync_engine
from app.models.result import QualityCheckResult
from config import settings
from app.api.quality_check_query import invalidate_quality_check_stats_cache

import redis
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Redis key 前缀
BATCH_PROGRESS_KEY_PREFIX = "batch:progress:"
BATCH_ERRORS_KEY_PREFIX = "batch:errors:"
BATCH_CANCEL_KEY_PREFIX = "batch:cancel:"


# === 姓名获取辅助函数 ===
_sales_map_cache = None

def _get_sales_map() -> dict:
    """获取销售 ID -> 姓名映射（带缓存）"""
    global _sales_map_cache
    if _sales_map_cache is None:
        sales_list = get_all_sales()
        _sales_map_cache = {s.get("user_id"): s.get("username") for s in sales_list if s.get("user_id")}
    return _sales_map_cache

def _get_user_name(user_id: str) -> str | None:
    """根据 user_id 获取销售姓名"""
    return _get_sales_map().get(user_id)

def _get_friend_name(user_id: str, friend_id: int) -> str | None:
    """根据 user_id 和 friend_id 获取好友姓名"""
    friends_list = get_friends_list(user_id)
    for f in friends_list:
        if f.get("friendId") == friend_id:
            return f.get("nick") or f.get("remark") or None
    return None


def _get_friend_info(user_id: str, friend_id: int) -> dict:
    """根据 user_id 和 friend_id 获取好友详细信息

    Returns:
        dict: 包含 friend_name, chat_title, alias, phone, remark_phone
    """
    friends_list = get_friends_list(user_id)
    for f in friends_list:
        if f.get("friendId") == friend_id:
            return {
                "friend_name": f.get("nick") or f.get("remark") or None,
                "chat_title": f.get("remark") or None,
                "alias": f.get("alias") or None,
                "phone": f.get("phone") or None,
                "remark_phone": f.get("remarkPhone") or None,
            }
    return {
        "friend_name": None,
        "chat_title": None,
        "alias": None,
        "phone": None,
        "remark_phone": None,
    }


def update_batch_progress(batch_task_id: str, completed: int, total: int, status: str = "running", **extra):
    """更新批量任务进度"""
    data = {"completed": completed, "total": total, "status": status}
    data.update(extra)
    redis_client.set(
        f"{BATCH_PROGRESS_KEY_PREFIX}{batch_task_id}",
        json.dumps(data),
        ex=3600
    )


def increment_batch_progress(batch_task_id: str):
    """原子性增加进度计数"""
    key = f"{BATCH_PROGRESS_KEY_PREFIX}{batch_task_id}"
    data = redis_client.get(key)
    if data:
        progress = json.loads(data)
        progress["completed"] = progress.get("completed", 0) + 1
        redis_client.set(key, json.dumps(progress), ex=3600)
        return progress
    return {"completed": 1, "total": 0, "status": "running"}


def get_batch_progress(batch_task_id: str) -> dict:
    """获取批量任务进度"""
    data = redis_client.get(f"{BATCH_PROGRESS_KEY_PREFIX}{batch_task_id}")
    if data:
        return json.loads(data)
    return {"completed": 0, "total": 0, "status": "pending"}


def record_batch_error(batch_task_id: str, user_id: str, friend_id: int, error: str):
    """记录失败的详细信息"""
    key = f"{BATCH_ERRORS_KEY_PREFIX}{batch_task_id}"
    error_info = {"user_id": user_id, "friend_id": friend_id, "error": error}
    redis_client.rpush(key, json.dumps(error_info))
    redis_client.expire(key, 3600)  # 1小时后过期


def get_batch_errors(batch_task_id: str) -> list:
    """获取批量任务的错误列表"""
    key = f"{BATCH_ERRORS_KEY_PREFIX}{batch_task_id}"
    errors = redis_client.lrange(key, 0, -1)
    return [json.loads(e) for e in errors]


def cancel_batch_task(batch_task_id: str) -> bool:
    """标记批量任务为取消状态"""
    key = f"{BATCH_CANCEL_KEY_PREFIX}{batch_task_id}"
    redis_client.set(key, "1", ex=3600)
    # 更新进度状态为取消中
    progress = get_batch_progress(batch_task_id)
    if progress.get("status") == "running":
        update_batch_progress(
            batch_task_id,
            completed=progress.get("completed", 0),
            total=progress.get("total", 0),
            status="cancelling"
        )
    return True


def is_batch_cancelled(batch_task_id: str) -> bool:
    """检查批量任务是否被取消"""
    key = f"{BATCH_CANCEL_KEY_PREFIX}{batch_task_id}"
    return redis_client.exists(key) > 0


def clear_batch_cancel(batch_task_id: str):
    """清除批量任务的取消标记"""
    key = f"{BATCH_CANCEL_KEY_PREFIX}{batch_task_id}"
    redis_client.delete(key)


@celery_app.task(bind=True, name="app.tasks.batch_quality.run_single_batch_check", rate_limit="20/m")
def run_single_batch_check(self, batch_task_id: str, user_id: str, friend_id: int,
                           start_time: str, end_time: str):
    """批量质检子任务：对单个聊天对进行质检分析"""
    # 检查任务是否被取消
    if is_batch_cancelled(batch_task_id):
        return {
            "status": "cancelled",
            "user_id": user_id,
            "friend_id": friend_id,
            "keyword_detected": "no",
        }

    try:
        # 获取聊天记录
        chat_records = get_chat_records(user_id, friend_id, start_time, end_time)

        if not chat_records:
            increment_batch_progress(batch_task_id)
            return {
                "status": "no_chat",
                "user_id": user_id,
                "friend_id": friend_id,
                "keyword_detected": "no",
            }

        # 执行质检分析
        result = quality_check_agent(
            user_id, friend_id, chat_records,
            start_time=start_time,
            end_time=end_time,
        )

        # 只有检测到关键词才保存到数据库
        if result.get("keyword_detected") == "yes":
            user_name = _get_user_name(user_id)
            friend_info = _get_friend_info(user_id, friend_id)
            with Session(sync_engine) as session:
                record = QualityCheckResult(
                    user_id=user_id,
                    user_name=user_name,
                    friend_id=friend_id,
                    friend_name=friend_info.get("friend_name"),
                    chat_title=friend_info.get("chat_title"),
                    alias=friend_info.get("alias"),
                    phone=friend_info.get("phone"),
                    remark_phone=friend_info.get("remark_phone"),
                    check_time_start=start_time,
                    check_time_end=end_time,
                    chat_record_count=result.get("chat_record_count", len(chat_records)),
                    keyword_detected=result.get("keyword_detected", "no"),
                    detected_keywords=result.get("detected_keywords"),
                    keyword_matches=result.get("keyword_matches"),
                    risk_level=result.get("risk_level"),
                    risk_category=result.get("risk_category"),
                    risk_description=result.get("risk_description"),
                    suggested_action=result.get("suggested_action"),
                    key_evidence=result.get("key_evidence"),
                    raw_response=result.get("raw_response"),
                    status=result.get("status", "success"),
                    batch_task_id=batch_task_id,
                    created_at=datetime.now(),
                )
                session.add(record)
                session.commit()

        # 更新进度
        increment_batch_progress(batch_task_id)

        return {
            "status": result.get("status", "success"),
            "user_id": user_id,
            "friend_id": friend_id,
            "keyword_detected": result.get("keyword_detected", "no"),
            "risk_level": result.get("risk_level"),
            "risk_category": result.get("risk_category"),
        }

    except Exception as e:
        increment_batch_progress(batch_task_id)
        record_batch_error(batch_task_id, user_id, friend_id, str(e))
        return {
            "status": "failed",
            "user_id": user_id,
            "friend_id": friend_id,
            "error": str(e),
        }


@celery_app.task(bind=True, name="app.tasks.batch_quality.on_batch_complete")
def on_batch_complete(self, results, batch_task_id: str):
    """批量质检完成回调：更新最终状态"""
    # 统计结果
    risk_count = sum(1 for r in results if r.get("keyword_detected") == "yes")
    no_chat_count = sum(1 for r in results if r.get("status") == "no_chat")
    failed_count = sum(1 for r in results if r.get("status") == "failed")
    cancelled_count = sum(1 for r in results if r.get("status") == "cancelled")

    # 检查是否是被取消的任务
    was_cancelled = is_batch_cancelled(batch_task_id)
    final_status = "cancelled" if was_cancelled else "completed"

    # 更新最终进度状态
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

    # 清除取消标记
    clear_batch_cancel(batch_task_id)

    # === 清除统计缓存 ===
    invalidate_quality_check_stats_cache()

    return {
        "status": final_status,
        "total_pairs": len(results),
        "risk_detected": risk_count,
        "no_chat": no_chat_count,
        "failed": failed_count,
        "cancelled": cancelled_count,
    }


@celery_app.task(bind=True, name="app.tasks.batch_quality.run_batch_quality_check")
def run_batch_quality_check(self, batch_task_id: str, start_time: str, end_time: str,
                            user_id_filter: str = None, limit: int = 500):
    """批量质检主任务：分析指定时间范围内所有有聊天记录的聊天对

    Args:
        batch_task_id: 批量任务ID
        start_time: 检测开始时间
        end_time: 检测结束时间
        user_id_filter: 可选，筛选特定销售ID
        limit: 最大分析数量
    """
    # 1. 获取聊天对列表（指定时间范围）
    pairs_data = get_chat_pairs(start_time, end_time)
    pairs = pairs_data.get("data", [])

    if not pairs:
        update_batch_progress(batch_task_id, 0, 0, "no_pairs")
        return {"status": "error", "message": "时间范围内无聊天记录"}

    # 2. 可选：按 user_id 筛选
    if user_id_filter:
        pairs = [p for p in pairs if p.get("user_id") == user_id_filter]

    # 3. 限制数量
    pairs = pairs[:limit]

    # 4. 初始化进度
    update_batch_progress(batch_task_id, 0, len(pairs), "running")

    # 5. 创建子任务列表
    subtasks = [
        run_single_batch_check.s(
            batch_task_id,
            p.get("user_id"),
            p.get("friend_id"),
            start_time,
            end_time,
        )
        for p in pairs
    ]

    # 6. 使用 chord：子任务完成后自动触发回调
    callback = on_batch_complete.s(batch_task_id)
    chord(subtasks)(callback)

    return {
        "status": "started",
        "total_pairs": len(pairs),
    }


@celery_app.task(bind=True, name="app.tasks.batch_quality.run_single_check_for_matched_pair")
def run_single_check_for_matched_pair(self, batch_task_id: str, user_id: str, friend_id: int,
                                      start_time: str, end_time: str):
    """处理单个匹配到关键词的销售-好友对"""
    # 检查任务是否被取消
    if is_batch_cancelled(batch_task_id):
        return {
            "status": "cancelled",
            "user_id": user_id,
            "friend_id": friend_id,
            "keyword_detected": "no",
        }

    try:
        # 获取完整聊天记录
        chat_records = get_chat_records(user_id, friend_id, start_time, end_time)

        if not chat_records:
            increment_batch_progress(batch_task_id)
            return {
                "status": "no_chat",
                "user_id": user_id,
                "friend_id": friend_id,
                "keyword_detected": "no",
            }

        # 执行质检分析
        result = quality_check_agent(
            user_id, friend_id, chat_records,
            start_time=start_time,
            end_time=end_time,
        )

        # 只有检测到关键词才保存到数据库
        if result.get("keyword_detected") == "yes":
            user_name = _get_user_name(user_id)
            friend_info = _get_friend_info(user_id, friend_id)
            with Session(sync_engine) as session:
                record = QualityCheckResult(
                    user_id=user_id,
                    user_name=user_name,
                    friend_id=friend_id,
                    friend_name=friend_info.get("friend_name"),
                    chat_title=friend_info.get("chat_title"),
                    alias=friend_info.get("alias"),
                    phone=friend_info.get("phone"),
                    remark_phone=friend_info.get("remark_phone"),
                    check_time_start=start_time,
                    check_time_end=end_time,
                    chat_record_count=result.get("chat_record_count", len(chat_records)),
                    keyword_detected=result.get("keyword_detected", "no"),
                    detected_keywords=result.get("detected_keywords"),
                    keyword_matches=result.get("keyword_matches"),
                    risk_level=result.get("risk_level"),
                    risk_category=result.get("risk_category"),
                    risk_description=result.get("risk_description"),
                    suggested_action=result.get("suggested_action"),
                    key_evidence=result.get("key_evidence"),
                    raw_response=result.get("raw_response"),
                    status=result.get("status", "success"),
                    batch_task_id=batch_task_id,
                    created_at=datetime.now(),
                )
                session.add(record)
                session.commit()

        # 更新进度
        increment_batch_progress(batch_task_id)

        return {
            "status": result.get("status", "success"),
            "user_id": user_id,
            "friend_id": friend_id,
            "keyword_detected": result.get("keyword_detected", "no"),
            "risk_level": result.get("risk_level"),
            "risk_category": result.get("risk_category"),
        }

    except Exception as e:
        increment_batch_progress(batch_task_id)
        record_batch_error(batch_task_id, user_id, friend_id, str(e))
        return {
            "status": "failed",
            "user_id": user_id,
            "friend_id": friend_id,
            "error": str(e),
        }


@celery_app.task(bind=True, name="app.tasks.batch_quality.run_batch_quality_check_by_messages")
def run_batch_quality_check_by_messages(self, batch_task_id: str, start_time: str, end_time: str,
                                        user_id_filter: str = None, limit: int = 500):
    """新批量质检：基于聊天记录的关键词匹配

    流程：
    1. 获取时间范围内所有聊天记录
    2. 对每条聊天记录进行关键词匹配
    3. 提取匹配到的销售ID和好友ID，去重
    4. 对去重后的销售-好友对进行质检分析

    Args:
        batch_task_id: 批量任务ID
        start_time: 检测开始时间
        end_time: 检测结束时间
        user_id_filter: 可选，筛选特定销售ID
        limit: 最大分析数量
    """
    from app.agents.quality_check import _get_active_keywords, _detect_keywords

    # 1. 获取所有聊天记录
    all_messages = get_all_chat_messages(start_time, end_time)

    if not all_messages:
        update_batch_progress(batch_task_id, 0, 0, "no_messages")
        return {"status": "error", "message": "时间范围内无聊天记录"}

    # 2. 获取启用的关键词列表
    keywords = _get_active_keywords()
    if not keywords:
        # 如果数据库没有关键词，使用默认配置（与 quality_check_agent 保持一致）
        keywords = [
            {"keyword": "退款", "category": "refund", "severity": "high"},
            {"keyword": "退费", "category": "refund", "severity": "high"},
            {"keyword": "退掉", "category": "refund", "severity": "medium"},
            {"keyword": "退钱", "category": "refund", "severity": "medium"},
            {"keyword": "返还", "category": "refund", "severity": "medium"},
            {"keyword": "投诉", "category": "complaint", "severity": "high"},
            {"keyword": "举报", "category": "complaint", "severity": "high"},
            {"keyword": "告你们", "category": "complaint", "severity": "high"},
            {"keyword": "取消订单", "category": "order_cancel", "severity": "medium"},
            {"keyword": "退订", "category": "order_cancel", "severity": "medium"},
            {"keyword": "不买了", "category": "order_cancel", "severity": "medium"},
            {"keyword": "工商", "category": "regulatory", "severity": "high"},
            {"keyword": "消费者协会", "category": "regulatory", "severity": "high"},
            {"keyword": "消协", "category": "regulatory", "severity": "high"},
            {"keyword": "12315", "category": "regulatory", "severity": "high"},
            {"keyword": "市场监管局", "category": "regulatory", "severity": "high"},
            {"keyword": "骗人", "category": "fraud", "severity": "medium"},
            {"keyword": "骗子", "category": "fraud", "severity": "medium"},
            {"keyword": "欺诈", "category": "fraud", "severity": "high"},
            {"keyword": "虚假宣传", "category": "fraud", "severity": "high"},
            {"keyword": "承诺没兑现", "category": "fraud", "severity": "medium"},
        ]

    # 3. 对每条聊天记录进行关键词匹配，提取匹配的销售-好友对
    matched_pairs = set()
    keyword_set = {kw["keyword"].lower() for kw in keywords}

    for message in all_messages:
        # 检查是否需要按销售ID筛选
        if user_id_filter and message.get("user_id") != user_id_filter:
            continue

        content = message.get("sentence", "")
        if content:
            content_lower = content.lower()
            for keyword_lower in keyword_set:
                if keyword_lower in content_lower:
                    user_id = message.get("user_id")
                    friend_id = message.get("friend_id")
                    if user_id and friend_id:
                        # friend_id 可能是字符串，需要转换为整数
                        try:
                            friend_id_int = int(friend_id)
                            matched_pairs.add((user_id, friend_id_int))
                        except (ValueError, TypeError):
                            pass
                    break  # 每条消息匹配到一个关键词即可

    # 4. 限制数量
    matched_pairs = list(matched_pairs)[:limit]

    if not matched_pairs:
        update_batch_progress(batch_task_id, 0, 0, "no_matches")
        return {"status": "completed", "message": "未匹配到任何关键词", "total_pairs": 0}

    # 5. 初始化进度
    update_batch_progress(batch_task_id, 0, len(matched_pairs), "running")

    # 6. 创建子任务列表
    subtasks = [
        run_single_check_for_matched_pair.s(
            batch_task_id,
            pair[0],  # user_id
            pair[1],  # friend_id
            start_time,
            end_time,
        )
        for pair in matched_pairs
    ]

    # 7. 使用 chord：子任务完成后自动触发回调
    callback = on_batch_complete.s(batch_task_id)
    chord(subtasks)(callback)

    return {
        "status": "started",
        "total_pairs": len(matched_pairs),
        "message": f"发现 {len(matched_pairs)} 个匹配关键词的销售-好友对",
    }