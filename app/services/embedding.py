# -*- coding: utf-8 -*-
"""DashScope Embedding 服务 — 直接 HTTP 调用（避免 LangChain 兼容性问题）"""
import httpx
from config import settings

# DashScope text-embedding-v3 使用 OpenAI 兼容接口
EMBEDDING_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"


def get_embedding(text: str, model: str = None) -> list[float]:
    """
    调用 DashScope embedding API，返回 1024 维向量。
    直接用 requests/httpx 调用，避免 LangChain OpenAIEmbeddings 的兼容性问题。
    """
    model = model or settings.EMBEDDING_MODEL
    resp = httpx.post(
        EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": text,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


def get_embeddings():
    """
    返回一个兼容对象，支持 .embed_documents(list[str]) 和 .embed_query(str) 调用。
    供 rag_service.py 和 populate_script_library.py 使用。
    """
    class _EmbeddingWrapper:
        @staticmethod
        def embed_documents(texts: list[str]) -> list[list[float]]:
            return [get_embedding(t) for t in texts]

        @staticmethod
        def embed_query(text: str) -> list[float]:
            return get_embedding(text)

    return _EmbeddingWrapper()
