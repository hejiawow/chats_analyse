# -*- coding: utf-8 -*-
"""督学跟进合规检测 Agent

你是专业的销售跟进合规检测Agent，**必须严格分步执行以下逻辑，禁止省略计算步骤，禁止返回0或空结果**，严格遵守所有规则：

=== 基础数据规则 ===
输入数据包含：销售ID、客户ID、全部聊天记录（含每条消息的时间戳、发送人）

=== 核心计算逻辑（不可修改） ===
1. 定位起始时间：提取聊天记录中【第一条消息的发送时间】，作为唯一计算起点T0
2. 划分固定时间窗口：
   - 窗口1：T0 至 T0+60天
   - 窗口2：T0+61天 至 T0+120天
   - 窗口3：T0+121天 至 T0+180天
   - 后续窗口以此类推，直到所有聊天记录结束
3. 统计每个窗口的有效数据：
   - 仅统计【销售发送的消息】
   - 计算【去重跟进天数】：同一天内销售无论发送多少条消息，仅计为1个跟进天数
4. 合规判定：
   - 标准：每个窗口要求去重跟进天数 ≥11天
   - 结果：若窗口去重天数 ＜11天 → 标记为【不合规窗口】

=== 强制输出要求 ===
1. 必须列出【所有不合规窗口】，不省略、不合并
2. 每个不合规窗口必须包含：
   - 窗口编号
   - 窗口时间范围（精确到日）
   - 该窗口实际去重跟进天数
   - 缺口天数（11-实际天数）
   - 判定结果（不合规）
3. 若无不合规窗口，才返回"全合规"；**只要有缺口，必须返回详情**

现在，请基于提供的销售跟进数据，执行完整计算并输出结果。
"""
from datetime import datetime, timedelta
from app.agents.registry import AgentRegistry

WINDOW_DAYS = 60
MIN_FOLLOW_UP_COUNT = 11


def _parse_timestamp(record: dict) -> datetime | None:
    """从聊天记录的 createTime 字段解析时间戳"""
    timestamp = record.get("createTime", "")
    if not timestamp:
        return None

    try:
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(timestamp, fmt)
                except ValueError:
                    continue
        return None
    except (ValueError, TypeError, OSError):
        return None


def _extract_sales_follow_up_dates(chat_records: list) -> list[datetime.date]:
    """提取销售发消息的日期列表（去重）"""
    dates = set()
    for record in chat_records:
        # 虎鲸 API：author="right" 表示销售（右侧）
        if record.get("author") != "right":
            continue

        dt = _parse_timestamp(record)
        if dt:
            dates.add(dt.date())

    return sorted(dates)


def _fixed_window_check(follow_up_dates: list[datetime.date], all_dates: list[datetime.date]) -> dict:
    """固定窗口算法：从第一条聊天记录起，每60天一个窗口"""
    if not follow_up_dates:
        return {
            "is_compliant": False,
            "reason": "无销售跟进记录",
            "total_follow_up_days": 0,
            "windows": [],
        }

    first_date = all_dates[0]
    last_date = all_dates[-1]
    total_span = (last_date - first_date).days

    # 按60天划分窗口：[0,60), [60,120), [120,180), ...
    windows = []
    window_start = first_date
    window_index = 0

    while window_start <= last_date:
        window_end = window_start + timedelta(days=WINDOW_DAYS)

        # 统计窗口内销售的跟进天数
        count = sum(1 for d in follow_up_dates if window_start <= d < window_end)

        is_compliant = count >= MIN_FOLLOW_UP_COUNT

        windows.append({
            "window_index": window_index + 1,
            "start": window_start.strftime("%Y-%m-%d"),
            "end": (window_end - timedelta(days=1)).strftime("%Y-%m-%d"),
            "count": count,
            "is_compliant": is_compliant,
        })

        window_start = window_end
        window_index += 1

    # 判断整体是否合规：所有窗口都满足11次才算合规
    overall_compliant = all(w["is_compliant"] for w in windows)

    violation_windows = [w for w in windows if not w["is_compliant"]]

    return {
        "is_compliant": overall_compliant,
        "total_follow_up_days": len(follow_up_dates),
        "chat_date_range": f"{first_date.strftime('%Y-%m-%d')} ~ {last_date.strftime('%Y-%m-%d')}",
        "total_span_days": total_span,
        "total_windows": len(windows),
        "violation_count": len(violation_windows),
        "windows": windows,
        "violation_windows": violation_windows,
    }


@AgentRegistry.register("督学跟进合规检测")
def follow_up_compliance_agent(user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
    """督学跟进合规检测 Agent"""
    if not chat_records:
        return {
            "status": "no_chat",
            "is_compliant": False,
            "reason": "无聊天记录",
        }

    # 1. 提取所有消息的日期（用于确定窗口起点和终点）
    all_dates = _extract_all_message_dates(chat_records)
    if not all_dates:
        return {
            "status": "no_chat",
            "is_compliant": False,
            "reason": "无有效时间戳",
        }

    # 2. 提取销售跟进日期
    follow_up_dates = _extract_sales_follow_up_dates(chat_records)

    # 3. 固定窗口检查
    result = _fixed_window_check(follow_up_dates, all_dates)

    # 4. 构建返回结果
    status = "compliant" if result["is_compliant"] else "non_compliant"

    return {
        "status": "success",
        "is_compliant": result["is_compliant"],
        "compliance_status": status,
        "total_follow_up_days": result.get("total_follow_up_days", 0),
        "chat_date_range": result.get("chat_date_range", ""),
        "total_windows": result.get("total_windows", 0),
        "violation_count": result.get("violation_count", 0),
        "violation_windows": result.get("violation_windows", []),
        "windows": result.get("windows", []),
        "reason": result.get("reason", ""),
    }


def _extract_all_message_dates(chat_records: list) -> list[datetime.date]:
    """提取所有消息的日期（用于确定聊天时间范围）"""
    dates = set()
    for record in chat_records:
        dt = _parse_timestamp(record)
        if dt:
            dates.add(dt.date())
    return sorted(dates)
