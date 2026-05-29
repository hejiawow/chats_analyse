# -*- coding: utf-8 -*-
"""转介绍检测 Agent — 基于 LangChain"""
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.agents.registry import AgentRegistry
from app.services.ai_client import get_llm
from app.prompts import load_prompt


def _prepare_sales_messages(chat_list: list, max_messages: int = 10000) -> str:
    sales_msgs = []
    for chat in chat_list:
        if chat.get("author") == "right":
            sales_msgs.append({
                "时间": chat.get("createTime", ""),
                "内容": chat.get("sentence", ""),
            })

    if not sales_msgs:
        return "无销售发送的消息"

    if len(sales_msgs) > max_messages:
        sales_msgs = sales_msgs[:max_messages]

    return json.dumps(sales_msgs, ensure_ascii=False, indent=2)


def _parse_ai_response(raw: str) -> dict:
    """解析 AI 响应，提取状态和多行证据"""
    status = "未发送"
    evidence_lines = []
    in_evidence_section = False

    for line in raw.split("\n"):
        line_strip = line.strip()
        # 检测状态行
        if "【转介绍发送状态】" in line_strip:
            status = "已发送" if "已发送" in line_strip else "未发送"
            in_evidence_section = False
        # 检测证据开始
        elif "【证据】" in line_strip:
            in_evidence_section = True
            # 如果证据行本身有内容（如 "【证据】：xxx"），提取冒号后的内容
            sep = "：" if "：" in line_strip else ":"
            after_sep = line_strip.split(sep, 1)[-1].strip() if sep in line_strip else ""
            if after_sep:
                evidence_lines.append(after_sep)
        # 收集证据内容（以数字序号开头或引号开头的行）
        elif in_evidence_section:
            # 遇到新段落标记则停止收集
            if line_strip.startswith("【") and "证据" not in line_strip:
                in_evidence_section = False
            elif line_strip and (line_strip[0].isdigit() or line_strip.startswith('"') or line_strip.startswith("'")):
                evidence_lines.append(line_strip)

    evidence = "\n".join(evidence_lines) if evidence_lines else "无"
    return {"status": status, "evidence": evidence, "raw_response": raw}


@AgentRegistry.register("转介绍检测")
def check_referral(user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
    """分析销售-好友聊天记录，判断是否发送了转介绍信息"""
    sales_msgs = _prepare_sales_messages(chat_records)

    if sales_msgs == "无销售发送的消息":
        return {"status": "未发送", "evidence": "无销售发送的消息"}

    # 使用 LangChain 构建 chain
    prompt = ChatPromptTemplate.from_template(load_prompt("referral_check"))
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()

    raw = chain.invoke({"chat_messages": sales_msgs})
    return _parse_ai_response(raw)
