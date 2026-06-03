# -*- coding: utf-8 -*-
"""协议退费过滤服务"""
import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import RefundWhitelistPattern
from app.services.hujing_api import get_chat_records

logger = logging.getLogger(__name__)


def get_whitelist_patterns(session: Session = None) -> list[str]:
    """从数据库获取启用的协议话术白名单

    Returns:
        list[str]: 启用的协议话术列表
    """
    if session is None:
        with Session(sync_engine) as session:
            patterns = session.query(RefundWhitelistPattern.pattern).filter(
                RefundWhitelistPattern.is_active == True
            ).all()
            return [p[0] for p in patterns]
    else:
        patterns = session.query(RefundWhitelistPattern.pattern).filter(
            RefundWhitelistPattern.is_active == True
        ).all()
        return [p[0] for p in patterns]


def _build_pair_index(all_messages: list) -> dict[tuple[str, int], list]:
    """按 (user_id, friend_id) 分组构建索引

    Args:
        all_messages: 批量接口获取的全部消息列表

    Returns:
        dict: {(user_id, friend_id): [messages]}
    """
    index: dict[tuple[str, int], list] = defaultdict(list)
    for msg in all_messages:
        user_id = msg.get("user_id")
        friend_id = msg.get("friend_id")
        if user_id and friend_id:
            try:
                index[(user_id, int(friend_id))].append(msg)
            except (ValueError, TypeError):
                pass
    return index


def _normalize_messages(messages: list) -> list:
    """将批量接口消息适配为 check_protocol_refund_trigger 所需格式

    批量接口字段: author, sentence, create_time
    过滤函数需要: author, sentence, createTime

    仅做 create_time → createTime 的字段映射，不修改原始数据。

    Args:
        messages: 批量接口返回的消息列表

    Returns:
        适配后的消息列表（新列表，不修改原始数据）
    """
    normalized = []
    for msg in messages:
        item = {
            "author": msg.get("author", ""),
            "sentence": msg.get("sentence", ""),
            "createTime": msg.get("create_time", "") or msg.get("createTime", ""),
        }
        normalized.append(item)
    return normalized


def check_protocol_refund_trigger(
    user_id: str,
    friend_id: int,
    chat_records: list,
    whitelist_patterns: list[str]
) -> bool:
    """检查是否为协议触发的退费

    Args:
        user_id: 销售ID
        friend_id: 好友ID
        chat_records: 聊天记录列表
        whitelist_patterns: 协议话术白名单列表

    Returns:
        True: 应过滤（协议触发退费）
        False: 不应过滤（正常质检）
    """
    if not chat_records or not whitelist_patterns:
        return False

    # 1. 按时间排序聊天记录
    sorted_records = sorted(chat_records, key=lambda r: r.get("createTime", ""))

    # 2. 找出销售发送的协议话术消息时间点
    protocol_times = []
    for record in sorted_records:
        if record.get("author") == "right":  # 销售
            content = record.get("sentence", "")
            for pattern in whitelist_patterns:
                if pattern in content:
                    protocol_times.append(record.get("createTime"))
                    break  # 每条消息匹配到一个即可

    if not protocol_times:
        return False

    # 3. 找出客户发送的退费关键词消息时间点
    refund_keywords = ["退费", "退款", "退钱", "退掉", "返还"]
    refund_times = []
    for record in sorted_records:
        if record.get("author") == "left":  # 客户
            content = record.get("sentence", "")
            for keyword in refund_keywords:
                if keyword in content:
                    refund_times.append(record.get("createTime"))
                    break  # 每条消息匹配到一个即可

    if not refund_times:
        return False

    # 4. 判断时间顺序：是否存在 协议话术 < 退费关键词
    for protocol_time in protocol_times:
        for refund_time in refund_times:
            if protocol_time and refund_time and protocol_time < refund_time:
                logger.info(f"[过滤] 销售:{user_id} 好友:{friend_id} 协议触发退费: 协议时间={protocol_time}, 退费时间={refund_time}")
                return True  # 协议触发退费，应过滤

    return False  # 不是协议触发，正常质检


def filter_matched_pairs(
    matched_pairs: list[tuple[str, int]],
    start_time: str,
    end_time: str,
    batch_task_id: str = None,
    log_func: callable = None,
    all_messages: Optional[list] = None
) -> list[tuple[str, int]]:
    """批量过滤匹配到的销售-好友对

    优先使用 all_messages 在内存中分组匹配（零 API 调用），
    若未提供 all_messages 则回退到逐对调 API 的旧逻辑。

    Args:
        matched_pairs: 匹配到的销售-好友对列表 [(user_id, friend_id)]
        start_time: 开始时间（回退模式使用）
        end_time: 结束时间（回退模式使用）
        batch_task_id: 批量任务ID（用于日志）
        log_func: 日志记录函数，签名为 (task_id, message, level)
        all_messages: 批量接口已获取的全部消息，传入后优先使用内存匹配

    Returns:
        过滤后的销售-好友对列表
    """
    if not matched_pairs:
        return matched_pairs

    # 获取协议话术白名单
    whitelist_patterns = get_whitelist_patterns()

    if not whitelist_patterns:
        if log_func and batch_task_id:
            log_func(batch_task_id, "[过滤] 协议话术白名单为空，跳过过滤步骤", "info")
        return matched_pairs

    if log_func and batch_task_id:
        log_func(batch_task_id, f"[过滤] 已加载 {len(whitelist_patterns)} 个协议话术白名单", "info")

    filtered_pairs = []
    filtered_count = 0

    # 优先使用内存匹配路径
    if all_messages is not None:
        if log_func and batch_task_id:
            log_func(batch_task_id, f"[过滤] 使用内存匹配模式（{len(all_messages)} 条消息，零 API 调用）", "info")

        pair_index = _build_pair_index(all_messages)

        for user_id, friend_id in matched_pairs:
            records = pair_index.get((user_id, friend_id), [])
            if not records:
                filtered_pairs.append((user_id, friend_id))
                continue

            normalized = _normalize_messages(records)

            if check_protocol_refund_trigger(user_id, friend_id, normalized, whitelist_patterns):
                filtered_count += 1
                if log_func and batch_task_id:
                    log_func(batch_task_id, f"[过滤] 销售:{user_id} 好友:{friend_id} 为协议触发退费，已过滤", "info")
            else:
                filtered_pairs.append((user_id, friend_id))

    else:
        # 回退：逐对调 API
        if log_func and batch_task_id:
            log_func(batch_task_id, "[过滤] 使用逐对请求模式", "info")

        for user_id, friend_id in matched_pairs:
            try:
                chat_records = get_chat_records(user_id, friend_id, start_time, end_time)

                if not chat_records:
                    filtered_pairs.append((user_id, friend_id))
                    continue

                if check_protocol_refund_trigger(user_id, friend_id, chat_records, whitelist_patterns):
                    filtered_count += 1
                    if log_func and batch_task_id:
                        log_func(batch_task_id, f"[过滤] 销售:{user_id} 好友:{friend_id} 为协议触发退费，已过滤", "info")
                else:
                    filtered_pairs.append((user_id, friend_id))

            except Exception as e:
                logger.error(f"[过滤] 销售:{user_id} 好友:{friend_id} 获取聊天记录失败: {e}")
                if log_func and batch_task_id:
                    log_func(batch_task_id, f"[过滤错误] 销售:{user_id} 好友:{friend_id} 获取聊天记录失败: {str(e)}", "error")
                filtered_pairs.append((user_id, friend_id))

    if log_func and batch_task_id and filtered_count > 0:
        log_func(batch_task_id, f"[过滤] 共过滤掉 {filtered_count} 个协议触发退费的聊天对", "info")

    return filtered_pairs
