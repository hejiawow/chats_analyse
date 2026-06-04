# -*- coding: utf-8 -*-
"""质检智能体 — 关键词预检测 + AI深度分析"""
import json
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import select

from app.agents.registry import AgentRegistry
from app.services.ai_client import get_llm
from app.services.ai_semaphore import get_ai_semaphore
from app.prompts import load_prompt
from app.models.database import sync_engine
from app.models.result import RiskKeyword
from sqlalchemy.orm import Session


ALLOWED_RISK_LEVELS = {"high", "medium", "low", "none", "unknown"}
ALLOWED_RISK_CATEGORIES = {"投诉", "退款", "取消订单", "监管介入", "虚假宣传", "服务不满", "其他"}
ALLOWED_TRIGGER_PARTIES = {"sales", "customer", "both", "none"}
ALLOWED_ACTION_PRIORITIES = {"P0", "P1", "P2", "P3"}
ALLOWED_RECOMMENDED_OWNERS = {"质检", "销售主管", "客服", "法务", "无需处理"}
ALLOWED_ACTION_TYPES = {"立即介入", "主管复核", "客服跟进", "销售安抚", "培训复盘", "误报观察", "无需处理"}
ALLOWED_FOLLOW_UP_DEADLINES = {"立即", "今日内", "24小时内", "3日内", "无需跟进"}


def _coerce_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是", "需要"}
    if value is None:
        return default
    return bool(value)


def _coerce_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _defaults_for_risk_level(risk_level: str) -> dict:
    if risk_level == "none":
        return {
            "action_priority": "P3",
            "recommended_owner": "无需处理",
            "action_type": "无需处理",
            "follow_up_deadline": "无需跟进",
            "needs_manual_review": False,
        }
    if risk_level == "low":
        return {
            "action_priority": "P2",
            "recommended_owner": "质检",
            "action_type": "误报观察",
            "follow_up_deadline": "24小时内",
            "needs_manual_review": False,
        }
    if risk_level == "medium":
        return {
            "action_priority": "P1",
            "recommended_owner": "质检",
            "action_type": "主管复核",
            "follow_up_deadline": "今日内",
            "needs_manual_review": True,
        }
    if risk_level == "high":
        return {
            "action_priority": "P0",
            "recommended_owner": "质检",
            "action_type": "立即介入",
            "follow_up_deadline": "立即",
            "needs_manual_review": True,
        }
    return {
        "action_priority": "P1",
        "recommended_owner": "质检",
        "action_type": "主管复核",
        "follow_up_deadline": "今日内",
        "needs_manual_review": True,
    }


def _normalize_quality_result(raw: dict | None) -> dict:
    """规范化 AI 质检结果，确保调用方拿到可落库字段。"""
    if not isinstance(raw, dict):
        raw = {}
    raw = raw or {}

    risk_level = raw.get("risk_level")
    if risk_level not in ALLOWED_RISK_LEVELS:
        risk_level = "unknown"

    defaults = _defaults_for_risk_level(risk_level)

    risk_category = raw.get("risk_category")
    if risk_category not in ALLOWED_RISK_CATEGORIES:
        risk_category = "其他"

    trigger_party = raw.get("trigger_party")
    if trigger_party not in ALLOWED_TRIGGER_PARTIES:
        trigger_party = None

    issue_summary = str(raw.get("issue_summary") or "").strip()
    if not issue_summary:
        issue_summary = "请人工复核质检结果" if risk_level == "unknown" else "未检测到明确风险"
    issue_summary = issue_summary[:50]

    action_priority = raw.get("action_priority")
    if action_priority not in ALLOWED_ACTION_PRIORITIES:
        action_priority = defaults["action_priority"]

    recommended_owner = raw.get("recommended_owner")
    if recommended_owner not in ALLOWED_RECOMMENDED_OWNERS:
        recommended_owner = defaults["recommended_owner"]

    action_type = raw.get("action_type")
    if action_type not in ALLOWED_ACTION_TYPES:
        action_type = defaults["action_type"]

    follow_up_deadline = raw.get("follow_up_deadline")
    if follow_up_deadline not in ALLOWED_FOLLOW_UP_DEADLINES:
        follow_up_deadline = defaults["follow_up_deadline"]

    guidance = raw.get("guidance")
    if not isinstance(guidance, dict):
        guidance = {}

    key_evidence = raw.get("key_evidence")
    if not isinstance(key_evidence, list):
        key_evidence = []

    return {
        "risk_level": risk_level,
        "risk_category": risk_category,
        "trigger_party": trigger_party,
        "issue_summary": issue_summary,
        "action_priority": action_priority,
        "recommended_owner": recommended_owner,
        "action_type": action_type,
        "follow_up_deadline": follow_up_deadline,
        "needs_manual_review": _coerce_bool(raw.get("needs_manual_review"), defaults["needs_manual_review"]),
        "confidence": _coerce_confidence(raw.get("confidence")),
        "guidance": guidance,
        "key_evidence": key_evidence,
    }


def _get_active_keywords() -> list[dict]:
    """从数据库获取所有启用的关键词"""
    with Session(sync_engine) as session:
        stmt = select(RiskKeyword).where(RiskKeyword.is_active == True)
        keywords = session.execute(stmt).scalars().all()
        return [
            {
                "keyword": kw.keyword,
                "category": kw.category,
                "severity": kw.severity,
            }
            for kw in keywords
        ]


def _detect_keywords(chat_records: list, keywords: list[dict]) -> dict:
    """关键词预检测（本地匹配）"""
    matches = []
    detected_keywords = set()
    keyword_set = {kw["keyword"].lower() for kw in keywords}
    keyword_info = {kw["keyword"].lower(): kw for kw in keywords}

    for record in chat_records:
        content = record.get("sentence", "")
        if not content:
            continue

        content_lower = content.lower()
        for keyword_lower in keyword_set:
            if keyword_lower in content_lower:
                kw_info = keyword_info.get(keyword_lower, {})
                detected_keywords.add(kw_info.get("keyword", keyword_lower))
                matches.append({
                    "keyword": kw_info.get("keyword", keyword_lower),
                    "category": kw_info.get("category", "unknown"),
                    "severity": kw_info.get("severity", "medium"),
                    "message": content[:200],  # 截取前200字符
                    "time": record.get("createTime", ""),
                    "speaker": "客户" if record.get("author") == "left" else "销售",
                })

    return {
        "detected": "yes" if matches else "no",
        "keywords": ",".join(detected_keywords) if detected_keywords else "",
        "keyword_matches": matches,
    }


def _prepare_context(chat_records: list, keyword_matches: list) -> list:
    """准备包含关键词的消息上下文（前后各取3条消息）"""
    keyword_times = set(m.get("time") for m in keyword_matches)

    context = []
    for i, record in enumerate(chat_records):
        if record.get("createTime") in keyword_times:
            # 取前后各3条消息作为上下文
            start_idx = max(0, i - 3)
            end_idx = min(len(chat_records), i + 4)
            context.extend(chat_records[start_idx:end_idx])

    # 去重并格式化
    seen = set()
    formatted = []
    for r in context:
        key = (r.get("createTime"), r.get("sentence", "")[:50])
        if key not in seen:
            seen.add(key)
            formatted.append({
                "角色": "销售" if r.get("author") == "right" else "客户",
                "时间": r.get("createTime", ""),
                "内容": r.get("sentence", ""),
            })

    return formatted


def _parse_ai_response(raw: str) -> dict:
    """解析 AI 响应（JSON格式）"""
    try:
        # 尝试提取 JSON 部分
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = raw[json_start:json_end]
            return _normalize_quality_result(json.loads(json_str))
    except json.JSONDecodeError:
        pass

    # 无法解析时返回默认值
    return _normalize_quality_result({
        "risk_level": "unknown",
        "risk_category": "其他",
        "trigger_party": None,
        "issue_summary": "AI响应解析失败，请人工复核",
        "action_priority": "P1",
        "recommended_owner": "质检",
        "action_type": "主管复核",
        "follow_up_deadline": "今日内",
        "needs_manual_review": True,
        "confidence": 0.0,
        "guidance": {
            "risk_reason": "AI响应无法解析，需人工查看聊天记录确认风险。",
            "customer_intent": "未知",
            "immediate_action": "请质检人员人工复核该聊天记录。",
            "reply_suggestion": "",
            "training_suggestion": "",
            "escalation_reason": "",
        },
        "key_evidence": [],
    })


def _ai_deep_analysis(chat_records: list, keyword_matches: list) -> dict:
    """AI深度分析（仅分析包含关键词的上下文，带并发控制和重试）"""
    # 准备上下文消息
    context_messages = _prepare_context(chat_records, keyword_matches)

    # 使用 LangChain 调用 AI（带并发控制）
    prompt = ChatPromptTemplate.from_template(load_prompt("quality_check"))
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()

    # 带重试的 AI 调用（每次重试都经过信号量）
    semaphore = get_ai_semaphore()
    max_retries = 3
    last_error = None

    for retry in range(max_retries):
        try:
            with semaphore:
                raw_response = chain.invoke({
                    "keyword_matches": json.dumps(keyword_matches, ensure_ascii=False, indent=2),
                    "context_messages": json.dumps(context_messages, ensure_ascii=False, indent=2),
                })

            # 成功，解析响应
            parsed = _parse_ai_response(raw_response)
            parsed["raw_response"] = raw_response
            return parsed

        except Exception as e:
            last_error = str(e)
            # 如果是 429 错误，继续重试
            if "429" in last_error and retry < max_retries - 1:
                print(f"AI call failed with 429, retrying ({retry + 1}/{max_retries})...")
                continue
            # 其他错误或最后一次重试失败，返回错误
            break

    # 所有重试都失败
    result = _normalize_quality_result({
        "risk_level": "unknown",
        "risk_category": "其他",
        "trigger_party": None,
        "issue_summary": "AI分析失败，请人工复核",
        "action_priority": "P1",
        "recommended_owner": "质检",
        "action_type": "主管复核",
        "follow_up_deadline": "今日内",
        "needs_manual_review": True,
        "guidance": {
            "risk_reason": f"AI分析失败: {last_error}",
            "customer_intent": "未知",
            "immediate_action": "请质检人员人工复核该聊天记录。",
            "reply_suggestion": "",
            "training_suggestion": "",
            "escalation_reason": "",
        },
        "key_evidence": [],
    })
    result["raw_response"] = None
    return result


@AgentRegistry.register("质检检测")
def quality_check_agent(
    user_id: str,
    friend_id: int,
    chat_records: list,
    start_time: str = None,
    end_time: str = None,
    **kwargs
) -> dict:
    """质检智能体主函数

    流程：
    1. 从数据库获取关键词配置
    2. 关键词预检测
    3. 若检测到关键词，触发AI深度分析
    4. 返回结构化结果
    """

    # 获取关键词配置
    keywords = _get_active_keywords()
    if not keywords:
        # 如果数据库没有关键词，使用默认配置
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

    # 步骤1: 关键词预检测
    keyword_result = _detect_keywords(chat_records, keywords)

    # 基础结果
    base_result = {
        "status": "success",
        "keyword_detected": keyword_result["detected"],
        "detected_keywords": keyword_result["keywords"],
        "keyword_matches": keyword_result["keyword_matches"],
        "chat_record_count": len(chat_records),
        "check_time_start": start_time,
        "check_time_end": end_time,
    }

    if keyword_result["detected"] == "no":
        # 未检测到关键词，直接返回
        base_result["status"] = "no_keyword"
        normalized = _normalize_quality_result({
            "risk_level": "none",
            "risk_category": "其他",
            "trigger_party": "none",
            "issue_summary": "未检测到风险关键词",
            "action_priority": "P3",
            "recommended_owner": "无需处理",
            "action_type": "无需处理",
            "follow_up_deadline": "无需跟进",
            "needs_manual_review": False,
            "confidence": 1.0,
            "guidance": {
                "risk_reason": "本地关键词预检测未命中风险关键词。",
                "customer_intent": "无明确风险诉求",
                "immediate_action": "无需处理",
                "reply_suggestion": "",
                "training_suggestion": "",
                "escalation_reason": "",
            },
            "key_evidence": [],
        })
        return {**base_result, **normalized}

    # 步骤2: AI深度分析（仅当检测到关键词时执行）
    ai_result = _ai_deep_analysis(chat_records, keyword_result["keyword_matches"])

    # 合并结果
    return {
        **base_result,
        "risk_level": ai_result.get("risk_level", "unknown"),
        "risk_category": ai_result.get("risk_category", "其他"),
        "trigger_party": ai_result.get("trigger_party"),
        "issue_summary": ai_result.get("issue_summary", ""),
        "action_priority": ai_result.get("action_priority"),
        "recommended_owner": ai_result.get("recommended_owner"),
        "action_type": ai_result.get("action_type"),
        "follow_up_deadline": ai_result.get("follow_up_deadline"),
        "needs_manual_review": ai_result.get("needs_manual_review"),
        "confidence": ai_result.get("confidence"),
        "guidance": ai_result.get("guidance", {}),
        "key_evidence": ai_result.get("key_evidence", []),
        "raw_response": ai_result.get("raw_response"),
    }
