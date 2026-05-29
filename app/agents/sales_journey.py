# -*- coding: utf-8 -*-
"""优秀成交案例提取 Agent — 销售复盘 / 话术萃取 / 成交拆解"""
import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage

from app.agents.registry import AgentRegistry
from app.services.ai_client import get_llm
from app.prompts import load_prompt

def _prepare_messages(chat_list: list, max_messages: int = 200) -> str:
    """准备完整对话记录，限制条数防止 token 溢出"""
    msgs = []
    for chat in chat_list:
        author = chat.get("author", "")
        role = "销售" if author == "right" else "客户"
        content = str(chat.get("sentence", ""))
        if len(content) > 500:
            content = content[:500] + "..."
        msgs.append({
            "角色": role,
            "时间": chat.get("createTime", ""),
            "内容": content,
        })

    if not msgs:
        return "无聊天记录"

    if len(msgs) > max_messages:
        msgs = msgs[:max_messages]

    return json.dumps(msgs, ensure_ascii=False, indent=2)


def _parse_ai_response(raw: str) -> dict:
    """解析 AI 返回的 JSON 结果"""
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {"status": "parse_failed", "raw_response": raw}


@AgentRegistry.register("优秀成交案例提取")
def extract_excellent_case(user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
    """分析成交聊天记录，提取优秀案例并生成复盘报告"""
    msgs = _prepare_messages(chat_records)

    if msgs == "无聊天记录":
        return {"status": "无聊天记录"}

    prompt_text = load_prompt("sales_journey").replace("{{chat_messages}}", msgs)
    prompt = ChatPromptTemplate([HumanMessage(content=prompt_text)])
    llm = get_llm()
    llm = llm.bind(response_format={"type": "json_object"})
    chain = prompt | llm | StrOutputParser()

    raw = chain.invoke({"chat_messages": msgs})
    parsed = _parse_ai_response(raw)
    if parsed.get("status") != "parse_failed":
        parsed["status"] = "已分析"

    # 修复 AI 可能将 module2~module6 嵌套在 module1_basic 内部的问题
    if "module1_basic" in parsed and isinstance(parsed["module1_basic"], dict):
        m1 = parsed["module1_basic"]
        for key in ["module2_journey", "module3_scripts", "module3_scenes", "module4_psychology",
                     "module5_key_factors", "module6_improvements"]:
            if key in m1 and key not in parsed:
                parsed[key] = m1.pop(key)

    # 兼容 module3_scenes → module3_scripts 的字段名
    if "module3_scenes" in parsed and "module3_scripts" not in parsed:
        parsed["module3_scripts"] = parsed.pop("module3_scenes")

    return parsed
