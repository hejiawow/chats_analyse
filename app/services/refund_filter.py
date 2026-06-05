# -*- coding: utf-8 -*-
"""协议退费过滤服务"""
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import RefundWhitelistPattern
from app.services.hujing_api import get_chat_friend_info, get_chat_records

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


def _has_customer_message(records: list) -> bool:
    """判断聊天记录中是否包含客户消息"""
    return any(record.get("author") == "left" for record in records)


def _get_quality_friend_name(friend: dict | None) -> str:
    """获取质检入口过滤使用的好友名来源字段。"""
    if not friend:
        return ""
    return friend.get("nick") or ""


def _should_filter_ahu_friend(friend_name: str | None) -> bool:
    """判断质检结果 friend_name 字段是否命中阿虎小号过滤规则"""
    if not friend_name:
        return False
    return "阿虎" in friend_name.strip()


def _build_friend_name_index(matched_pairs: list[tuple[str, int]],
                              log_func: callable = None,
                              batch_task_id: str = None) -> dict[int, str]:
    """通过全局唯一 friend_id 构建 friend_id -> nick 映射"""
    friend_ids = sorted({friend_id for _, friend_id in matched_pairs if friend_id})
    if not friend_ids:
        return {}

    if log_func and batch_task_id:
        log_func(batch_task_id, f"[过滤] 需要通过精准好友接口获取 {len(friend_ids)} 个好友昵称...", "info")

    friend_name_index: dict[int, str] = {}
    max_workers = min(10, len(friend_ids))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_friend_id = {
            executor.submit(get_chat_friend_info, friend_id): friend_id
            for friend_id in friend_ids
        }
        for future in as_completed(future_to_friend_id):
            friend_id = future_to_friend_id[future]
            try:
                friend_name = _get_quality_friend_name(future.result())
            except Exception as e:
                logger.error(f"[过滤] 获取好友 {friend_id} 昵称失败: {e}")
                continue

            if friend_name:
                friend_name_index[friend_id] = friend_name

    if log_func and batch_task_id:
        log_func(batch_task_id, f"[过滤] 精准好友接口获取完成，共索引 {len(friend_name_index)} 个好友昵称", "info")

    return friend_name_index


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

    # 获取协议话术白名单。新增的入口级过滤不依赖白名单，因此白名单为空时不能提前返回。
    whitelist_patterns = get_whitelist_patterns()

    if not whitelist_patterns:
        if log_func and batch_task_id:
            log_func(batch_task_id, "[过滤] 协议话术白名单为空，跳过协议退费过滤", "info")
    elif log_func and batch_task_id:
        log_func(batch_task_id, f"[过滤] 已加载 {len(whitelist_patterns)} 个协议话术白名单", "info")

    filtered_pairs = []
    filtered_count = 0

    # 优先使用内存匹配路径
    if all_messages is not None:
        if log_func and batch_task_id:
            log_func(batch_task_id, f"[过滤] 使用内存匹配模式（{len(all_messages)} 条消息，零 API 调用）", "info")

        pair_index = _build_pair_index(all_messages)
        try:
            friend_name_index = _build_friend_name_index(matched_pairs, log_func, batch_task_id)
        except Exception as e:
            logger.error(f"[过滤] 获取好友信息失败: {e}")
            if log_func and batch_task_id:
                log_func(batch_task_id, f"[过滤错误] 获取好友信息失败: {str(e)}", "error")
            friend_name_index = {}

        for user_id, friend_id in matched_pairs:
            records = pair_index.get((user_id, friend_id), [])
            if not records:
                filtered_pairs.append((user_id, friend_id))
                continue

            if not _has_customer_message(records):
                filtered_count += 1
                if log_func and batch_task_id:
                    log_func(batch_task_id, f"[过滤] 销售:{user_id} 好友:{friend_id} 无客户消息，已过滤", "info")
                continue

            friend_name = friend_name_index.get(friend_id)
            if _should_filter_ahu_friend(friend_name):
                filtered_count += 1
                if log_func and batch_task_id:
                    log_func(batch_task_id, f"[过滤] 销售:{user_id} 好友:{friend_id} 好友昵称包含阿虎，已过滤", "info")
                continue

            normalized = _normalize_messages(records)

            if whitelist_patterns and check_protocol_refund_trigger(user_id, friend_id, normalized, whitelist_patterns):
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

                if whitelist_patterns and check_protocol_refund_trigger(user_id, friend_id, chat_records, whitelist_patterns):
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
        log_func(batch_task_id, f"[过滤] 共过滤掉 {filtered_count} 个聊天对", "info")

    return filtered_pairs
