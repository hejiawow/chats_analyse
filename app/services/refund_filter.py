# -*- coding: utf-8 -*-
"""协议退费过滤服务"""
import logging
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
    log_func: callable = None
) -> list[tuple[str, int]]:
    """批量过滤匹配到的销售-好友对

    Args:
        matched_pairs: 匹配到的销售-好友对列表 [(user_id, friend_id)]
        start_time: 开始时间
        end_time: 结束时间
        batch_task_id: 批量任务ID（用于日志）
        log_func: 日志记录函数，签名为 (task_id, message, level)

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

    for user_id, friend_id in matched_pairs:
        try:
            # 获取该聊天对的聊天记录
            chat_records = get_chat_records(user_id, friend_id, start_time, end_time)

            if not chat_records:
                # 无聊天记录，保留（后续质检流程会处理）
                filtered_pairs.append((user_id, friend_id))
                continue

            # 检查是否为协议触发退费
            if check_protocol_refund_trigger(user_id, friend_id, chat_records, whitelist_patterns):
                # 应过滤
                filtered_count += 1
                if log_func and batch_task_id:
                    log_func(batch_task_id, f"[过滤] 销售:{user_id} 好友:{friend_id} 为协议触发退费，已过滤", "info")
            else:
                # 不应过滤，保留
                filtered_pairs.append((user_id, friend_id))

        except Exception as e:
            logger.error(f"[过滤] 销售:{user_id} 好友:{friend_id} 获取聊天记录失败: {e}")
            if log_func and batch_task_id:
                log_func(batch_task_id, f"[过滤错误] 销售:{user_id} 好友:{friend_id} 获取聊天记录失败: {str(e)}", "error")
            # 出错时保留，由后续质检流程处理
            filtered_pairs.append((user_id, friend_id))

    if log_func and batch_task_id and filtered_count > 0:
        log_func(batch_task_id, f"[过滤] 共过滤掉 {filtered_count} 个协议触发退费的聊天对", "info")

    return filtered_pairs