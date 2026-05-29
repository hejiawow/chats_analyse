# -*- coding: utf-8 -*-
"""
话术库数据填充脚本
从 case_extraction_results 提取高分案例 → 生成 embedding → 写入 case_script_library
运行方式：python -m app.scripts.populate_script_library
"""
import os
import sys
import time

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    os.environ['PGCLIENTENCODING'] = 'UTF8'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import sync_engine
from app.models.result import CaseExtractionResult
from app.models.script_lib import CaseScriptLibrary
from app.services.embedding import get_embeddings


def build_document_text(case) -> str:
    """将案例各字段拼接为 embedding 文本"""
    parts = []
    if case.applicable_scenario:
        parts.append(f"场景：{case.applicable_scenario}")
    if case.script_type == "销售话术" and case.customer_question:
        parts.append(f"客户问题：{case.customer_question}")
    if case.script_type == "唤醒话术" and case.trigger_customer_state:
        parts.append(f"触发状态：{case.trigger_customer_state}")
    if case.target_audience:
        parts.append(f"适配人群：{case.target_audience}")
    if case.customer_profile:
        parts.append(f"客户画像：{case.customer_profile}")
    if case.customer_intent:
        parts.append(f"沟通阶段：{case.customer_intent}")
    if case.sales_answer or case.wake_script:
        quote = case.sales_answer or case.wake_script
        parts.append(f"销售话术：{quote}")
    if case.core_design_logic:
        parts.append(f"设计逻辑：{case.core_design_logic}")
    if case.key_techniques:
        parts.append(f"关键技巧：{case.key_techniques}")
    if case.pitfall_avoid:
        parts.append(f"反例避坑：{case.pitfall_avoid}")
    if case.tags:
        parts.append(f"标签：{case.tags}")
    if case.business_subject:
        parts.append(f"业务科目：{case.business_subject}")
    if case.compliance_risk and case.compliance_risk != "无合规风险":
        parts.append(f"合规风险：{case.compliance_risk}")
    return "\n".join(parts)


def is_high_score(case) -> bool:
    """判断是否为有效案例：有销售话术原文或唤醒话术原文即可入库"""
    quote = case.sales_answer or case.wake_script
    return bool(quote and quote.strip())


def main():
    print("=== 开始填充话术库 ===")
    embeddings = get_embeddings()

    with Session(sync_engine) as session:
        # 查询所有成功的案例
        stmt = select(CaseExtractionResult).where(
            CaseExtractionResult.status == "success"
        )
        cases = session.execute(stmt).scalars().all()
        print(f"共找到 {len(cases)} 条成功案例")

        # 获取已入库的 source_case_id（断点续传）
        existing_ids = set()
        existing_stmt = select(CaseScriptLibrary.source_case_id)
        for row in session.execute(existing_stmt).scalars().all():
            if row:
                existing_ids.add(row)

        # 筛选高分且未入库的案例
        to_embed = [c for c in cases if is_high_score(c) and c.id not in existing_ids]
        print(f"高分且未入库：{len(to_embed)} 条")

        if not to_embed:
            print("无需填充，退出。")
            return

        success_count = 0
        fail_count = 0

        for i, case in enumerate(to_embed, 1):
            doc_text = build_document_text(case)
            if not doc_text.strip():
                print(f"  [{i}/{len(to_embed)}] SKIP: 案例 {case.id} 无有效文本")
                continue

            try:
                # 调用 DashScope embedding API
                vec = embeddings.embed_documents([doc_text])[0]

                record = CaseScriptLibrary(
                    source_case_id=case.id,
                    user_id=case.user_id,
                    user_wx_id=case.user_wx_id,
                    friend_id=case.friend_id,
                    friend_wx_id=case.friend_wx_id,
                    friend_nick=case.friend_nick,
                    scenario_type=case.applicable_scenario or "",
                    customer_type=case.target_audience or "",
                    communication_stage=case.customer_intent or "",
                    sales_quote=case.sales_answer or case.wake_script or "",
                    comprehensive_review=case.core_design_logic or "",
                    customer_profile=case.customer_profile or "",
                    document_text=doc_text,
                    embedding=vec,
                )
                session.add(record)
                session.commit()
                success_count += 1
                print(f"  [{i}/{len(to_embed)}] OK: 案例 {case.id} ({case.scenario_type})")

                # 避免 API 限流
                time.sleep(0.3)

            except Exception as e:
                session.rollback()
                fail_count += 1
                print(f"  [{i}/{len(to_embed)}] FAIL: 案例 {case.id} - {e}")

    print(f"\n=== 填充完成 ===")
    print(f"成功: {success_count} 条, 失败: {fail_count} 条")


if __name__ == "__main__":
    main()
