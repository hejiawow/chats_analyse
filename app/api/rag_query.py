# -*- coding: utf-8 -*-
"""RAG 问答 API"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.rag_service import retrieve_similar_cases, generate_rag_answer
from app.services.dependencies import require_permission, get_current_user

router = APIRouter()


class RAGAskRequest(BaseModel):
    query: str
    top_k: int = 5
    scenario_type: str | None = None
    customer_type: str | None = None
    min_score: int = 3


class RAGAskResponse(BaseModel):
    answer: str
    sources: list[dict]
    query: str


@router.post("/rag/ask")
async def rag_ask(
    req: RAGAskRequest,
    current_user: dict = Depends(require_permission("read:rag")),
):
    """
    RAG 问答接口。
    1. 向量检索相关案例
    2. 基于案例生成回答
    """
    cases = retrieve_similar_cases(
        query=req.query,
        top_k=req.top_k,
        scenario_type=req.scenario_type,
        customer_type=req.customer_type,
        min_score=req.min_score,
    )

    result = generate_rag_answer(query=req.query, cases=cases)

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "query": req.query,
        "case_count": len(cases),
    }
