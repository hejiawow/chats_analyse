# -*- coding: utf-8 -*-
"""AI 调用服务（LangChain + DashScope）"""
import json

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import settings
from app.services.ai_semaphore import get_ai_semaphore


def get_llm(model: str = None) -> ChatOpenAI:
    """获取 LangChain LLM 实例"""
    return ChatOpenAI(
        model=model or settings.AI_MODEL,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.AI_API_URL,
        temperature=0.1,
        timeout=300,
        max_retries=0,  # 禁用内置重试，由信号量控制并发
    )


def call_ai(prompt: str, system_prompt: str = "", model: str = None) -> str:
    """调用 AI，返回文本（带并发控制）"""
    try:
        semaphore = get_ai_semaphore()
        with semaphore:  # 获取信号量槽位，限制并发
            messages = [("system", system_prompt), ("user", "{input}")] if system_prompt else [("user", "{input}")]
            chat_prompt = ChatPromptTemplate.from_messages(messages)
            chain = chat_prompt | get_llm(model) | StrOutputParser()
            return chain.invoke({"input": prompt})
    except Exception as e:
        return f"AI分析失败：{str(e)}"


def call_ai_json(prompt: str, system_prompt: str = "", model: str = None) -> dict:
    """调用 AI 并要求返回 JSON（带并发控制）"""
    try:
        semaphore = get_ai_semaphore()
        with semaphore:  # 获取信号量槽位，限制并发
            messages = [("system", system_prompt), ("user", "{input}")] if system_prompt else [("user", "{input}")]
            chat_prompt = ChatPromptTemplate.from_messages(messages)
            llm = get_llm(model)
            llm = llm.bind(response_format={"type": "json_object"})
            chain = chat_prompt | llm | StrOutputParser()
            raw = chain.invoke({"input": prompt})
            return json.loads(raw)
    except Exception as e:
        return {"error": f"AI分析失败：{str(e)}"}
