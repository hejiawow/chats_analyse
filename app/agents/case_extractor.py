# -*- coding: utf-8 -*-
"""阿虎医考优秀销售案例提炼 Agent — 基于 LangChain"""
import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.agents.registry import AgentRegistry
from app.services.ai_client import get_llm
from app.prompts import load_prompt


def _prepare_messages(chat_list: list, max_messages: int = 300) -> str:
    """准备完整对话记录（含双方），用于案例分析"""
    msgs = []
    for chat in chat_list:
        author = chat.get("author", "")
        role = "销售" if author == "right" else "客户"
        msgs.append({
            "角色": role,
            "时间": chat.get("createTime", ""),
            "内容": chat.get("sentence", ""),
        })

    if not msgs:
        return "无聊天记录"

    if len(msgs) > max_messages:
        msgs = msgs[:max_messages]

    return json.dumps(msgs, ensure_ascii=False, indent=2)


def _parse_ai_response(raw: str) -> dict:
    """解析 AI 返回的话术提取结果 — JSON 格式"""
    raw = raw.strip()

    # 1. 尝试直接解析 JSON
    parsed = _extract_json(raw)
    if parsed and isinstance(parsed, dict):
        scripts = parsed.get("scripts", [])
        summary = parsed.get("summary", {})
        # 为缺少 script_type 的 scripts 补充默认值
        for s in scripts:
            if not s.get("script_type"):
                s["script_type"] = "销售话术"
        # 转换为向后兼容的 cases 格式
        cases = _scripts_to_cases(scripts)
        return {
            "status": "已提炼" if cases else "无显著优秀案例",
            "cases_count": len(cases),
            "scripts": scripts,  # 保留原始 scripts 供 _save_cases 使用
            "cases": cases,
            "summary": summary,
            "raw_response": raw,
        }

    # 2. JSON 解析失败，降级为文本解析（兼容旧格式）
    fallback = _parse_text_fallback(raw)
    # 为降级结果补充 scripts（从 cases 反推）
    if fallback.get("cases"):
        fallback["scripts"] = [
            {
                "script_type": "销售话术",
                "customer_question": c.get("客户问题", ""),
                "sales_answer": c.get("销售原话", ""),
                "scene_tag": c.get("场景类型", ""),
                "customer_intent": c.get("当前沟通阶段", ""),
                "tags": c.get("可复制性说明", ""),
                "business_subject": "",
                "compliance_risk": "",
                "why_good": c.get("销售能力说明", ""),
                "customer_profile": c.get("客户类型判断", ""),
                "anti_pitfall": c.get("细节借鉴说明", ""),
            }
            for c in fallback["cases"]
        ]
    return fallback


def _extract_json(text: str) -> dict:
    """从 LLM 返回中提取并解析 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取代码块中的 JSON
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试匹配最外层 JSON 对象
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _scripts_to_cases(scripts: list) -> list:
    """将 scripts JSON 转换为向后兼容的 cases 格式"""
    cases = []
    for s in scripts:
        case_data = {
            "场景类型": s.get("scene_tag", ""),
            "客户类型判断": s.get("customer_profile", ""),
            "当前沟通阶段": s.get("customer_intent", ""),
            "销售原话": s.get("sales_answer", ""),
            "销售能力评分": 0,
            "销售能力说明": s.get("why_good", ""),
            "可复制性评分": 0,
            "可复制性说明": s.get("tags", ""),
            "细节借鉴评分": 0,
            "细节借鉴说明": s.get("anti_pitfall", ""),
            "综合点评": "",
        }
        # 至少要有销售原话才算有效案例
        if case_data.get("销售原话"):
            cases.append(case_data)
    return cases


def _parse_text_fallback(raw: str) -> dict:
    """降级文本解析（兼容旧格式）"""
    cases = []
    summary = ""

    case_blocks = re.split(r'\uff08?\u3010优秀案例\s*#\d+\u3011\uff09?', raw)
    if len(case_blocks) <= 1:
        case_blocks = re.split(r'【优秀案例\s*#\d+】', raw)

    for block in case_blocks[1:]:
        block = block.strip()
        if not block:
            continue

        case_data = {
            "场景类型": "", "客户类型判断": "", "当前沟通阶段": "",
            "销售原话": "", "销售能力评分": 0, "销售能力说明": "",
            "可复制性评分": 0, "可复制性说明": "",
            "细节借鉴评分": 0, "细节借鉴说明": "", "综合点评": "",
        }

        for line in block.split("\n"):
            line = line.strip()
            for key in case_data.keys():
                if line.startswith(key + "\uff1a") or line.startswith(key + ":"):
                    sep = "\uff1a" if "\uff1a" in line else ":"
                    value = line.split(sep, 1)[-1].strip()
                    if "\u8bc4\u5206" in key:  # "评分"
                        m = re.search(r'(\d)', value)
                        case_data[key] = int(m.group(1)) if m else 0
                    else:
                        case_data[key] = value

        if case_data.get("\u573a\u666f\u7c7b\u578b") or case_data.get("\u9500\u552e\u539f\u8bdd"):
            cases.append(case_data)

    if "\u3010\u603b\u7ed3\u5efa\u8bae\u3011" in raw:
        idx = raw.index("\u3010\u603b\u7ed3\u5efa\u8bae\u3011")
        summary = raw[idx:].strip()

    return {
        "status": "\u5df2\u63d0\u70bc" if cases else "\u65e0\u663e\u8457\u4f18\u79c0\u6848\u4f8b",
        "cases_count": len(cases),
        "cases": cases,
        "summary": summary,
        "raw_response": raw,
    }


@AgentRegistry.register("优秀话术提取")
def extract_sales_cases(user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
    """分析销售-好友聊天记录，基于阿虎医考销售方法论提炼优秀案例"""
    msgs = _prepare_messages(chat_records)

    if msgs == "无聊天记录":
        return {"status": "无聊天记录", "cases": [], "cases_count": 0}

    # 使用 LangChain 链式调用
    prompt = ChatPromptTemplate.from_template(
        load_prompt("case_extraction"),
        template_format="jinja2"
    )
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke({"chat_messages": msgs})
    return _parse_ai_response(raw)
