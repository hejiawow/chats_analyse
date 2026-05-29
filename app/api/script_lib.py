# -*- coding: utf-8 -*-
"""话术库查询 API — pgvector 向量检索"""
import numpy as np
from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, func, distinct, text, cast, Float
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.script_lib import CaseScriptLibrary
from app.services.dependencies import require_permission, get_current_user

router = APIRouter()


@router.get("/script-lib")
async def query_script_lib(
    scenario_type: str | None = Query(None, description="场景类型"),
    customer_type: str | None = Query(None, description="客户类型"),
    keyword: str | None = Query(None, description="关键词搜索"),
    min_score: int | None = Query(3, ge=1, le=5, description="最低评分"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("read:scriptlib")),
):
    """话术库分页查询（基于 PostgreSQL，支持 ILIKE 关键词）"""
    with Session(sync_engine) as session:
        base = select(CaseScriptLibrary).where(
            CaseScriptLibrary.status == "active"
        )
        count_base = select(func.count()).where(
            CaseScriptLibrary.status == "active"
        )

        if scenario_type:
            base = base.where(CaseScriptLibrary.scenario_type.ilike(f"%{scenario_type}%"))
            count_base = count_base.where(CaseScriptLibrary.scenario_type.ilike(f"%{scenario_type}%"))
        if customer_type:
            base = base.where(CaseScriptLibrary.customer_type.ilike(f"%{customer_type}%"))
            count_base = count_base.where(CaseScriptLibrary.customer_type.ilike(f"%{customer_type}%"))
        if keyword:
            like = f"%{keyword}%"
            base = base.where(
                CaseScriptLibrary.sales_quote.ilike(like)
                | CaseScriptLibrary.comprehensive_review.ilike(like)
                | CaseScriptLibrary.scenario_type.ilike(like)
            )
            count_base = count_base.where(
                CaseScriptLibrary.sales_quote.ilike(like)
                | CaseScriptLibrary.comprehensive_review.ilike(like)
                | CaseScriptLibrary.scenario_type.ilike(like)
            )
        if min_score:
            base = base.where(CaseScriptLibrary.sales_ability_score >= min_score)
            count_base = count_base.where(CaseScriptLibrary.sales_ability_score >= min_score)

        total = session.scalar(count_base)
        records = session.execute(
            base.order_by(CaseScriptLibrary.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": [r.to_dict() for r in records],
        }


@router.get("/script-lib/scenarios")
async def get_scenario_types(current_user: dict = Depends(require_permission("read:scriptlib"))):
    """获取所有去重的场景类型列表（前端下拉用）"""
    with Session(sync_engine) as session:
        rows = session.execute(
            select(distinct(CaseScriptLibrary.scenario_type))
            .where(
                CaseScriptLibrary.status == "active",
                CaseScriptLibrary.scenario_type.isnot(None),
            )
            .order_by(CaseScriptLibrary.scenario_type)
        ).scalars().all()

        return {"scenarios": [r for r in rows if r]}


@router.get("/script-lib/stats")
async def get_script_stats(current_user: dict = Depends(require_permission("read:scriptlib"))):
    """话术库统计信息"""
    with Session(sync_engine) as session:
        total = session.scalar(
            select(func.count()).where(CaseScriptLibrary.status == "active")
        )
        scenarios = session.execute(
            select(CaseScriptLibrary.scenario_type, func.count())
            .where(CaseScriptLibrary.status == "active")
            .group_by(CaseScriptLibrary.scenario_type)
            .order_by(func.count().desc())
        ).all()

        avg_scores = session.execute(
            select(
                func.avg(CaseScriptLibrary.sales_ability_score),
                func.avg(CaseScriptLibrary.replicability_score),
                func.avg(CaseScriptLibrary.detail_score),
            ).where(CaseScriptLibrary.status == "active")
        ).first()

        return {
            "total": total,
            "scenarios": [{"name": r[0], "count": r[1]} for r in scenarios if r[0]],
            "avg_scores": {
                "sales_ability": round(float(avg_scores[0] or 0), 1),
                "replicability": round(float(avg_scores[1] or 0), 1),
                "detail": round(float(avg_scores[2] or 0), 1),
            },
        }


@router.get("/script-lib/similar/{case_id}")
async def get_similar_scripts(
    case_id: int, top_k: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(require_permission("read:scriptlib")),
):
    """向量相似度搜索 — 找与指定案例相似的话术（pgvector HNSW 余弦距离）"""
    with Session(sync_engine) as session:
        record = session.execute(
            select(CaseScriptLibrary).where(CaseScriptLibrary.id == case_id)
        ).scalar_one_or_none()

        if not record or record.embedding is None:
            return {"error": "记录不存在或未嵌入"}

        q_vec = np.array(record.embedding)

        # pgvector 余弦距离运算符 <=> 走 HNSW 索引
        stmt = (
            select(
                CaseScriptLibrary,
                cast(CaseScriptLibrary.embedding.op("<=>")(q_vec), Float).label("distance"),
            )
            .where(
                CaseScriptLibrary.id != case_id,
                CaseScriptLibrary.status == "active",
                CaseScriptLibrary.embedding.isnot(None),
            )
            .order_by(text("distance"))
            .limit(top_k)
        )

        results = session.execute(stmt).all()

        return {
            "source_id": case_id,
            "source_scenario": record.scenario_type,
            "data": [
                {**r[0].to_dict(), "similarity": round((1 - float(r[1])) * 100, 1)}
                for r in results
            ],
        }


@router.get("/script-lib/{case_id}")
async def get_script_detail(
    case_id: int,
    current_user: dict = Depends(require_permission("read:scriptlib")),
):
    """单条话术详情"""
    with Session(sync_engine) as session:
        record = session.execute(
            select(CaseScriptLibrary).where(CaseScriptLibrary.id == case_id)
        ).scalar_one_or_none()

        if not record:
            return {"error": "记录不存在"}
        return record.to_dict()
