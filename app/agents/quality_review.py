# -*- coding: utf-8 -*-
"""质检二次审查智能体 — 风险等级复核"""
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.agents.registry import AgentRegistry
from app.services.ai_client import get_llm
from app.services.ai_semaphore import get_ai_semaphore
from app.prompts import load_prompt

ALLOWED_SECONDARY_RISK_LEVELS = {"high", "medium", "low", "none", "unknown"}
ALLOWED_SUGGESTED_ACTIONS = {"立即介入", "主管复核", "客服跟进", "销售安抚", "培训复盘", "误报观察", "无需处理"}
ALLOWED_RISK_TYPES = {"退费", "投诉", "其他"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}


def _coerce_confidence(value) -> float:
    """规范化置信度到0-1范围"""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_review_result(raw: dict | None) -> dict:
    """规范化二次审查结果"""
    if not isinstance(raw, dict):
        raw = {}

    secondary_risk_level = raw.get("secondary_risk_level")
    if secondary_risk_level not in ALLOWED_SECONDARY_RISK_LEVELS:
        secondary_risk_level = "unknown"

    review_reason = str(raw.get("review_reason") or "").strip()
    if not review_reason:
        review_reason = "AI响应缺少判断理由，请人工复核"

    suggested_action = raw.get("suggested_action")
    if suggested_action not in ALLOWED_SUGGESTED_ACTIONS:
        suggested_action = "主管复核"

    confidence = _coerce_confidence(raw.get("confidence"))

    # 新增字段：confirmed
    confirmed = raw.get("confirmed")
    if isinstance(confirmed, bool):
        pass
    elif isinstance(confirmed, str):
        confirmed = confirmed.strip().lower() in {"true", "1", "yes", "是"}
    else:
        confirmed = None

    # 新增字段：risk_type
    risk_type = raw.get("risk_type")
    if risk_type not in ALLOWED_RISK_TYPES:
        risk_type = "其他"

    # 新增字段：priority
    priority = raw.get("priority")
    if priority not in ALLOWED_PRIORITIES:
        priority = "P2"

    # 新增字段：first_mention_time
    first_mention_time = str(raw.get("first_mention_time") or "").strip() or None

    return {
        "confirmed": confirmed,
        "risk_type": risk_type,
        "priority": priority,
        "first_mention_time": first_mention_time,
        "secondary_risk_level": secondary_risk_level,
        "review_reason": review_reason[:500],
        "suggested_action": suggested_action,
        "confidence": confidence,
    }


def _parse_ai_response(raw: str) -> dict:
    """解析AI响应（JSON格式）"""
    try:
        # 尝试提取JSON部分
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = raw[json_start:json_end]
            return _normalize_review_result(json.loads(json_str))
    except json.JSONDecodeError:
        pass

    # 无法解析时返回默认值
    return _normalize_review_result({
        "confirmed": None,
        "risk_type": "其他",
        "priority": "P2",
        "first_mention_time": None,
        "secondary_risk_level": "unknown",
        "review_reason": "AI响应解析失败，请人工复核",
        "suggested_action": "主管复核",
        "confidence": 0.0,
    })


def _format_chat_records(chat_records: list) -> str:
    """格式化聊天记录为文本"""
    formatted = []
    for record in chat_records:
        role = "销售" if record.get("author") == "right" else "客户"
        time = record.get("createTime", "")
        content = record.get("sentence", "")
        formatted.append(f"【{role}】{time}: {content}")

    return "\n".join(formatted)


def _format_key_evidence(key_evidence: list) -> str:
    """格式化关键证据为文本"""
    if not key_evidence:
        return "无关键证据"

    formatted = []
    for evidence in key_evidence:
        content = evidence.get("content", "")
        time = evidence.get("time", "")
        speaker = evidence.get("speaker", "")
        formatted.append(f"【{speaker}】{time}: {content}")

    return "\n".join(formatted)


@AgentRegistry.register("质检二次审查")
def quality_review_agent(
    result_id: int,
    chat_records: list,
    key_evidence: list,
    issue_summary: str,
    initial_risk_level: str,
    raw_response: str = "",
    **kwargs
) -> dict:
    """质检二次审查Agent主函数

    流程：
    1. 格式化输入信息（聊天记录、关键证据、第一次AI原始分析结果）
    2. 调用AI进行风险等级复核（带并发控制）
    3. 解析和规范化结果
    4. 返回结构化数据
    """

    # 格式化输入
    formatted_chat_records = _format_chat_records(chat_records)
    formatted_key_evidence = _format_key_evidence(key_evidence)
    initial_raw_response = raw_response or "无第一次分析结果"

    # 使用LangChain调用AI（带并发控制）
    prompt = ChatPromptTemplate.from_template(load_prompt("quality_review"))
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()

    # 带重试的AI调用
    semaphore = get_ai_semaphore()
    max_retries = 3
    last_error = None

    for retry in range(max_retries):
        try:
            with semaphore:
                ai_response = chain.invoke({
                    "initial_risk_level": initial_risk_level,
                    "raw_response": initial_raw_response,
                    "chat_records": formatted_chat_records,
                })

            # 成功，解析响应
            parsed = _parse_ai_response(ai_response)
            parsed["raw_response"] = ai_response
            parsed["status"] = "success"
            return parsed

        except Exception as e:
            last_error = str(e)
            # 如果是429错误，继续重试
            if "429" in last_error and retry < max_retries - 1:
                print(f"AI call failed with 429, retrying ({retry + 1}/{max_retries})...")
                continue
            # 其他错误或最后一次重试失败，返回错误
            break

    # 所有重试都失败
    result = _normalize_review_result({
        "confirmed": None,
        "risk_type": "其他",
        "priority": "P2",
        "first_mention_time": None,
        "secondary_risk_level": "unknown",
        "review_reason": f"AI分析失败: {last_error}",
        "suggested_action": "主管复核",
        "confidence": 0.0,
    })
    result["raw_response"] = None
    result["status"] = "failed"
    result["error_msg"] = last_error
    return result
