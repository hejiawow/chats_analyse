# -*- coding: utf-8 -*-
"""查询分析结果 API — 统一统计"""
from datetime import datetime
from fastapi import APIRouter
from sqlalchemy import select

from app.models.database import async_session
from app.models.result import ReferralResult, CaseExtractionResult, SalesJourneyResult, FollowUpComplianceResult

router = APIRouter()


@router.get("/stats")
async def get_stats():
    """获取工作台统计信息"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    async with async_session() as session:
        # 转介绍统计
        ref_stmt = select(ReferralResult).where(ReferralResult.created_at >= today_start)
        ref_result = await session.execute(ref_stmt)
        referral_records = ref_result.scalars().all()
        referral_sent = sum(1 for r in referral_records if r.result.get("status") == "已发送")
        referral_not_sent = sum(1 for r in referral_records if r.result.get("status") == "未发送")

        # 案例提取统计
        case_stmt = select(CaseExtractionResult).where(CaseExtractionResult.created_at >= today_start)
        case_result = await session.execute(case_stmt)
        case_records = case_result.scalars().all()
        case_count = len([r for r in case_records if r.status == "success"])

        # 成交案例统计
        sj_stmt = select(SalesJourneyResult).where(SalesJourneyResult.created_at >= today_start)
        sj_result = await session.execute(sj_stmt)
        sj_records = sj_result.scalars().all()
        sj_count = len([r for r in sj_records if r.status == "success"])

        # 督学跟进合规统计
        fu_stmt = select(FollowUpComplianceResult).where(FollowUpComplianceResult.created_at >= today_start)
        fu_result = await session.execute(fu_stmt)
        fu_records = fu_result.scalars().all()
        fu_compliant = len([r for r in fu_records if r.is_compliant == "compliant"])
        fu_non_compliant = len([r for r in fu_records if r.is_compliant == "non_compliant"])

        # 总任务数
        today_total = len(referral_records) + len(case_records) + len(sj_records) + len(fu_records)

        # 活跃智能体
        active_agents = len({
            "转介绍检测" if referral_records else None,
            "优秀话术提取" if case_records else None,
            "优秀成交案例提取" if sj_records else None,
            "督学跟进合规检测" if fu_records else None,
        }.difference({None}))

        return {
            "today_tasks": today_total,
            "referral_sent": referral_sent,
            "referral_not_sent": referral_not_sent,
            "cases_found": case_count,
            "cases_with_results": case_count,
            "sj_count": sj_count,
            "fu_compliant": fu_compliant,
            "fu_non_compliant": fu_non_compliant,
            "active_agents": active_agents,
        }
