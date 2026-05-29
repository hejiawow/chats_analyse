# -*- coding: utf-8 -*-
"""RAG 核心服务 — pgvector HNSW 向量检索 + AI 生成回答"""
import numpy as np
from sqlalchemy import select, text, cast, Float
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.script_lib import CaseScriptLibrary
from app.services.embedding import get_embeddings
from app.services.ai_client import get_llm


def retrieve_similar_cases(
    query: str,
    top_k: int = 5,
    scenario_type: str | None = None,
    customer_type: str | None = None,
    min_score: int = 3,
) -> list[dict]:
    """
    将查询文本 embedding，使用 pgvector HNSW 索引进行余弦相似度检索，
    返回 top-K 高分案例。
    """
    embeddings = get_embeddings()
    query_vec = embeddings.embed_query(query)

    with Session(sync_engine) as session:
        # pgvector 余弦距离：<=> 运算符，值越小越相似
        # 使用 order by embedding <=> :vec 走 HNSW 索引
        stmt = (
            select(
                CaseScriptLibrary,
                cast(CaseScriptLibrary.embedding.op("<=>")(np.array(query_vec)), Float).label("distance"),
            )
            .where(
                CaseScriptLibrary.status == "active",
                CaseScriptLibrary.embedding.isnot(None),
            )
            .order_by(text("distance"))
            .limit(top_k)
        )

        if scenario_type:
            stmt = stmt.where(CaseScriptLibrary.scenario_type.ilike(f"%{scenario_type}%"))
        if customer_type:
            stmt = stmt.where(CaseScriptLibrary.customer_type.ilike(f"%{customer_type}%"))
        if min_score:
            stmt = stmt.where(CaseScriptLibrary.sales_ability_score >= min_score)

        results = session.execute(stmt).all()

        if not results:
            return []

        return [
            {
                **rec.to_source(),
                "similarity": round((1 - float(dist)) * 100, 1),
            }
            for rec, dist in results
        ]


def generate_rag_answer(
    query: str,
    cases: list[dict],
) -> dict:
    """
    将检索到的案例构建为 context prompt，调用 LLM 生成回答。
    返回 {"answer": str, "sources": [...]}
    """
    if not cases:
        return {
            "answer": "抱歉，在当前话术库中未找到与您的问题相关的案例。请尝试更换关键词或扩大搜索范围。",
            "sources": [],
        }

    # 构建上下文
    context_parts = []
    for i, c in enumerate(cases, 1):
        parts = []
        parts.append(f"### 案例 {i}")
        if c.get("scenario_type"):
            parts.append(f"场景：{c['scenario_type']}")
        if c.get("communication_stage"):
            parts.append(f"阶段：{c['communication_stage']}")
        if c.get("sales_quote"):
            parts.append(f"销售话术：{c['sales_quote']}")
        if c.get("comprehensive_review"):
            parts.append(f"点评：{c['comprehensive_review']}")
        parts.append(f"评分：销售能力 {c.get('sales_ability_score')}/5，可复制性 {c.get('replicability_score')}/5，细节 {c.get('detail_score')}/5")
        context_parts.append("\n".join(parts))

    context_text = "\n\n".join(context_parts)

    prompt = f"""你是一位专业的销售培训顾问。请根据以下话术库案例，回答用户的问题。

## 相关案例参考

{context_text}

## 用户问题

{query}

## 回答要求

1. 基于上述案例中的实际经验和话术来回答，不要编造不存在的内容
2. 给出具体可操作的建议和话术示例
3. 如果案例信息不足以给出完整建议，请明确说明局限性
4. 回答使用中文，语气专业且易懂
5. 在回答末尾标注"以上建议基于 {len(cases)} 个相关案例"
"""

    llm = get_llm()
    try:
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        answer = f"生成回答时出错：{str(e)}"

    return {
        "answer": answer,
        "sources": [{"id": c["id"], "scenario_type": c.get("scenario_type"), "sales_quote": c.get("sales_quote", "")[:200]} for c in cases],
    }
