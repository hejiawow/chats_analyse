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
from app.services.voice_transcription_service import voice_service
from app.prompts import load_prompt
from app.models.database import sync_engine
from app.models.result import RiskKeyword
from sqlalchemy.orm import Session


def _resolve_voice_url(voice_path: str) -> str:
    """
    补全语音文件URL

    如果voice_path是相对路径，补全为完整URL
    """
    from config import settings

    # 如果已经是完整URL，直接返回
    if voice_path.startswith("http://") or voice_path.startswith("https://"):
        return voice_path

    # 获取文件服务基础URL
    file_base_url = settings.HUJING_FILE_BASE_URL

    # 如果未配置，从API基础URL推断
    if not file_base_url and settings.HUJING_API_BASE_URL:
        # 从 https://hj.ahujiaoyu.com:9029 提取 https://hj.ahujiaoyu.com
        import re
        match = re.match(r"(https?://[^/]+)", settings.HUJING_API_BASE_URL)
        if match:
            file_base_url = match.group(1).replace(":9029", "").replace(":80", "").replace(":443", "")

    if not file_base_url:
        # 无法补全，返回原路径
        return voice_path

    # 构建完整URL
    # 格式: https://hj.ahujiaoyu.com/srb/common/file?path={voice_path}&app_id={app_id}
    encoded_path = voice_path.replace("/", "%2F")
    return f"{file_base_url}/srb/common/file?path={encoded_path}&app_id={settings.HUJING_APP_ID}"


def _transcribe_voice_messages(chat_records: list) -> tuple[list, dict]:
    """
    将聊天记录中的语音消息转换为文字

    使用 VoiceTranscriptionService 批量转写

    Args:
        chat_records: 原始聊天记录列表

    Returns:
        (处理后的聊天记录, 转写统计信息)
    """
    # 使用新的语音转写服务
    processed_records, stats = voice_service.transcribe_chat_records(chat_records)

    # 转换统计格式兼容旧代码
    return processed_records, {
        "transcribed_count": stats["success"],
        "error_count": stats["failed"],
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
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 无法解析时返回默认值
    return {
        "risk_level": "unknown",
        "risk_category": "未知",
        "trigger_party": None,
        "risk_description": "AI响应解析失败",
        "suggested_action": "请人工复核",
        "key_evidence": [],
    }


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
    return {
        "risk_level": "unknown",
        "risk_category": "未知",
        "trigger_party": None,
        "risk_description": f"AI分析失败: {last_error}",
        "suggested_action": "请人工复核",
        "key_evidence": [],
        "raw_response": None,
    }


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
    1. 语音消息转文字（如有）
    2. 从数据库获取关键词配置
    3. 关键词预检测
    4. 若检测到关键词，触发AI深度分析
    5. 返回结构化结果
    """

    # 步骤1: 语音消息转文字（替换sentence中的URL为转写文字）
    chat_records, voice_stats = _transcribe_voice_messages(chat_records)

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
        "voice_transcribed_count": voice_stats["transcribed_count"],
        "voice_transcribe_error_count": voice_stats["error_count"],
    }

    if keyword_result["detected"] == "no":
        # 未检测到关键词，直接返回
        base_result["status"] = "no_keyword"
        base_result["risk_level"] = "none"
        base_result["risk_category"] = "无风险"
        base_result["trigger_party"] = None
        base_result["risk_description"] = "未检测到风险关键词"
        base_result["suggested_action"] = "无需处理"
        base_result["key_evidence"] = []
        return base_result

    # 步骤2: AI深度分析（仅当检测到关键词时执行）
    ai_result = _ai_deep_analysis(chat_records, keyword_result["keyword_matches"])

    # 直接使用AI返回的trigger_party
    trigger_party = ai_result.get("trigger_party")
    # 校验trigger_party值是否合法
    if trigger_party not in ("sales", "customer", "both", "none"):
        trigger_party = None

    # 合并结果
    return {
        **base_result,
        "risk_level": ai_result.get("risk_level", "unknown"),
        "risk_category": ai_result.get("risk_category", "未知"),
        "trigger_party": trigger_party,
        "risk_description": ai_result.get("risk_description", ""),
        "suggested_action": ai_result.get("suggested_action", ""),
        "key_evidence": ai_result.get("key_evidence", []),
        "raw_response": ai_result.get("raw_response"),
    }