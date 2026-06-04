# -*- coding: utf-8 -*-
"""分析任务 Worker — 带实时日志"""
import json
import logging
import traceback
import time
from datetime import datetime
from app.celery_app import celery_app
from app.services.hujing_api import get_chat_records
from app.services.datasource.manager import DataSourceManager
from app.agents.registry import AgentRegistry
import app.agents  # noqa: F401 - 触发所有 Agent 的注册
from app.models.result import ReferralResult, CaseExtractionResult, SalesJourneyResult, FollowUpComplianceResult, QualityCheckResult, QualityCheckDetail
from app.models.database import sync_engine
from config import settings
from app.services.log_service import log as _log, get_task_logs, mark_task_done, is_task_done, clear_task_logs

# 使用 Redis 存储日志和任务状态（跨进程共享）
import redis
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# 本地线程锁（仅用于本地操作）
import threading
_task_logs_lock = threading.Lock()




def _save_referral(user_id, user_wx_id, friend_id, friend_wx_id, friend_nick,
                   status, result, error_msg=None):
    """保存转介绍检测结果"""
    return ReferralResult(
        user_id=user_id, user_wx_id=user_wx_id,
        friend_id=friend_id, friend_wx_id=friend_wx_id, friend_nick=friend_nick,
        status=status, result=result, error_msg=error_msg, created_at=datetime.now(),
    )


def _save_cases(user_id, user_wx_id, friend_id, friend_wx_id, friend_nick,
                raw_result: dict):
    """将每条优秀话术保存为独立记录（支持销售话术 + 唤醒话术）

    仅处理 JSON 格式输出（scripts 数组，英文键名）。
    """
    scripts = raw_result.get("scripts", [])
    if not scripts:
        # 兼容旧 cases 格式（中文键名）
        for case in raw_result.get("cases", []):
            script = {
                "script_type": "销售话术",
                "customer_question": case.get("销售原话", "")[:50] + "..." if case.get("销售原话") else "",
                "sales_answer": case.get("销售原话", ""),
                "scene_tag": case.get("场景类型", ""),
                "customer_intent": case.get("当前沟通阶段", ""),
                "tags": case.get("可复制性说明", ""),
                "business_subject": "",
                "compliance_risk": "",
                "why_good": case.get("销售能力说明", ""),
                "customer_profile": case.get("客户类型判断", ""),
                "anti_pitfall": case.get("细节借鉴说明", ""),
            }
            scripts.append(script)

    records = []
    for script in scripts:
        script_type = script.get("script_type", "")

        # 通用字段（优先英文键名，兼容中文键名）
        common = {
            "applicable_scenario": script.get("scene_tag", "") or script.get("适用场景", ""),
            "tags": script.get("tags", "") or script.get("标签", ""),
            "business_subject": script.get("business_subject", "") or script.get("业务科目", ""),
            "compliance_risk": script.get("compliance_risk", "") or script.get("合规风险", ""),
            "core_design_logic": script.get("why_good", "") or script.get("核心设计逻辑", ""),
            "key_techniques": script.get("tags", "") or script.get("话术关键技巧", ""),
            "pitfall_avoid": script.get("anti_pitfall", "") or script.get("反例避坑", ""),
            "customer_profile": script.get("customer_profile", "") or script.get("客户画像", ""),
        }

        # 类型专属字段
        if script_type == "唤醒话术":
            record = CaseExtractionResult(
                user_id=user_id, user_wx_id=user_wx_id,
                friend_id=friend_id, friend_wx_id=friend_wx_id,
                friend_nick=friend_nick,
                script_type="唤醒话术",
                trigger_customer_state=script.get("trigger_customer_state", "") or script.get("触发客户状态", ""),
                wake_script=script.get("wake_script", "") or script.get("销冠唤醒话术原文", ""),
                script_objective=script.get("script_objective", "") or script.get("话术核心目标", ""),
                target_audience=script.get("target_audience", "") or script.get("适配人群", ""),
                **common,
                raw_response=raw_result.get("raw_response", ""),
                status="success",
                created_at=datetime.now(),
            )
        else:
            # 默认按销售话术处理
            record = CaseExtractionResult(
                user_id=user_id, user_wx_id=user_wx_id,
                friend_id=friend_id, friend_wx_id=friend_wx_id,
                friend_nick=friend_nick,
                script_type="销售话术",
                customer_question=script.get("customer_question", "") or script.get("客户问题", ""),
                sales_answer=script.get("sales_answer", "") or script.get("销冠回答", ""),
                customer_intent=script.get("customer_intent", "") or script.get("客户意图", ""),
                **common,
                raw_response=raw_result.get("raw_response", ""),
                status="success",
                created_at=datetime.now(),
            )

        records.append(record)

    return records


@celery_app.task(bind=True, name="app.tasks.analysis.run_analysis", max_retries=3)
def run_analysis(self, task_id: str, user_id: str, friend_id: int,
                 user_wx_id: str = None, friend_wx_id: str = None,
                 friend_nick: str = None, agent: str = "all",
                 datasource: str = "hujing",
                 start_time: str = None,
                 end_time: str = None):
    """执行分析任务：拉聊天记录 → 跑所有 Agent → 分别存结果到对应表

    Args:
        agent: "all" 执行所有 Agent，或 "referral"/"case"/"journey"/"follow_up"/"quality_check" 执行单个 Agent
        datasource: 数据源标识，默认为 "hujing"
        start_time: 聊天记录起始时间（可选）
        end_time: 聊天记录结束时间（可选）
    """
    # 清理旧日志
    clear_task_logs(task_id)

    print(f"[Task {task_id}] 开始执行 | agent={agent}, datasource={datasource}")
    _log(task_id, f"开始分析 | 销售: {user_id}, 好友: {friend_id}, 数据源: {datasource}")
    try:
        # 获取数据源实例
        ds = DataSourceManager.get(datasource)
        if not ds:
            _log(task_id, f"未知数据源: {datasource}", "error")
            print(f"[Task {task_id}] 未知数据源: {datasource}")
            mark_task_done(task_id)
            return {"status": "error", "message": f"未知数据源: {datasource}"}

        # 1. 拉取聊天记录
        _log(task_id, f"正在从 {ds.get_display_name()} 拉取聊天记录...", "info")
        if start_time and end_time:
            _log(task_id, f"时间范围: {start_time} 至 {end_time}", "info")
        print(f"[Task {task_id}] 步骤1: 开始拉取聊天记录")
        t1 = time.time()
        chat_records = ds.get_chat_records(
            user_id, friend_id,
            start_time=start_time,
            end_time=end_time,
        )
        print(f"[Task {task_id}] 步骤1: 拉取完成，耗时 {time.time()-t1:.1f}s，共 {len(chat_records)} 条")
        _log(task_id, f"获取聊天记录 {len(chat_records)} 条 (耗时 {time.time()-t1:.1f}s)", "success")

        if not chat_records:
            _log(task_id, "聊天记录为空，无法分析", "warning")
            print(f"[Task {task_id}] 聊天记录为空")
            mark_task_done(task_id)
            return {"status": "empty", "message": "无聊天记录"}

        # 2. 跑所有已注册的 Agent（逐个执行+记录）
        results = {}
        
        # 根据 agent 参数决定执行哪些 Agent
        agent_map = {
            "referral": ["转介绍检测"],
            "case": ["优秀话术提取"],
            "journey": ["优秀成交案例提取"],
            "follow_up": ["督学跟进合规检测"],
            "quality_check": ["质检检测"],
        }
        
        if agent == "all":
            agents_to_run = AgentRegistry.list_all()
        else:
            # 支持逗号分隔的多个智能体
            agents_to_run = []
            for agent_name in agent.split(','):
                agent_name = agent_name.strip()
                if agent_name in agent_map:
                    agents_to_run.extend(agent_map[agent_name])
                else:
                    _log(task_id, f"未知的 agent 参数: {agent_name}", "error")
                    print(f"[Task {task_id}] 未知的 agent: {agent_name}")
                    mark_task_done(task_id)
                    return {"status": "error", "message": f"未知的 agent 参数: {agent_name}"}
            if not agents_to_run:
                _log(task_id, f"未指定有效的智能体: {agent}", "error")
                print(f"[Task {task_id}] 未指定有效的智能体: {agent}")
                mark_task_done(task_id)
                return {"status": "error", "message": f"未指定有效的智能体"}

        print(f"[Task {task_id}] 步骤2: 开始执行 Agent，共 {len(agents_to_run)} 个")
        _log(task_id, f"准备执行 {len(agents_to_run)} 个 Agent: {', '.join(agents_to_run)}", "info")

        for idx, agent_name in enumerate(agents_to_run, 1):
            _log(task_id, f"[{idx}/{len(agents_to_run)}] 正在执行 Agent: {agent_name}...", "info")
            print(f"[Task {task_id}] 步骤2.{idx}: 开始执行 {agent_name}")
            t0 = time.time()
            try:
                func = AgentRegistry.get(agent_name)
                print(f"[Task {task_id}] 步骤2.{idx}: 调用 {agent_name} 函数...")
                # 传递时间参数给 Agent（质检智能体需要）
                result = func(
                    user_id, friend_id, chat_records,
                    start_time=start_time,
                    end_time=end_time,
                )
                elapsed = time.time() - t0
                print(f"[Task {task_id}] 步骤2.{idx}: {agent_name} 完成，耗时 {elapsed:.1f}s")
                
                status = result.get("status", "")
                cases_count = result.get("cases_count", 0)
                detail = f"{status}"
                if cases_count:
                    detail += f", 提取 {cases_count} 个案例"
                _log(task_id, f"  [{agent_name}] 完成 ({elapsed:.1f}s): {detail}", "success")
                results[agent_name] = result
            except Exception as e:
                elapsed = time.time() - t0
                print(f"[Task {task_id}] 步骤2.{idx}: {agent_name} 失败: {e}")
                traceback.print_exc()
                _log(task_id, f"  [{agent_name}] 失败 ({elapsed:.1f}s): {e}", "error")
                results[agent_name] = {"status": "error", "error": str(e)}

        # 3. 分别保存结果
        _log(task_id, "正在保存分析结果到数据库...", "info")
        print(f"[Task {task_id}] 步骤3: 开始保存结果到数据库")
        from sqlalchemy.orm import Session
        t3 = time.time()
        with Session(sync_engine) as session:
            saved = 0
            for agent_name, result in results.items():
                print(f"[Task {task_id}] 步骤3: 保存 {agent_name} 结果")
                if agent_name == "转介绍检测":
                    record = _save_referral(
                        user_id, user_wx_id, friend_id, friend_wx_id, friend_nick,
                        "success", result,
                    )
                    session.add(record)
                    saved += 1

                elif agent_name == "优秀话术提取":
                    if result.get("status") == "无显著优秀案例":
                        record = CaseExtractionResult(
                            user_id=user_id, user_wx_id=user_wx_id,
                            friend_id=friend_id, friend_wx_id=friend_wx_id,
                            friend_nick=friend_nick,
                            status="no_cases",
                            raw_response=result.get("raw_response", ""),
                            error_msg="该聊天记录中无显著优秀案例",
                            created_at=datetime.now(),
                        )
                        session.add(record)
                        _log(task_id, f"  [{agent_name}] 未发现优秀案例", "warning")
                    else:
                        case_records = _save_cases(
                            user_id, user_wx_id, friend_id, friend_wx_id, friend_nick,
                            result,
                        )
                        summary = result.get("summary")
                        for cr in case_records:
                            cr.summary = summary
                            session.add(cr)
                            saved += 1
                        _log(task_id, f"  [{agent_name}] 保存 {len(case_records)} 个案例", "success")

                elif agent_name == "优秀成交案例提取":
                    if result.get("status") == "无聊天记录":
                        record = SalesJourneyResult(
                            user_id=user_id, user_wx_id=user_wx_id,
                            friend_id=friend_id, friend_wx_id=friend_wx_id,
                            friend_nick=friend_nick,
                            status="no_chat",
                            error_msg="无聊天记录",
                            created_at=datetime.now(),
                        )
                    else:
                        basic = result.get("module1_basic", {})
                        record = SalesJourneyResult(
                            user_id=user_id,
                            user_wx_id=user_wx_id,
                            friend_id=friend_id,
                            friend_wx_id=friend_wx_id,
                            friend_nick=friend_nick,
                            analysis_result=result,
                            deal_time=basic.get("deal_time", ""),
                            chat_duration=basic.get("chat_duration", ""),
                            message_count=basic.get("message_count"),
                            sales_style=basic.get("sales_style", ""),
                            raw_response=result.get("raw_response", ""),
                            status="success",
                            created_at=datetime.now(),
                        )
                    session.add(record)
                    saved += 1
                    _log(task_id, f"  [{agent_name}] 保存成交分析报告", "success")

                elif agent_name == "督学跟进合规检测":
                    if result.get("status") == "no_chat":
                        record = FollowUpComplianceResult(
                            user_id=user_id, user_wx_id=user_wx_id,
                            friend_id=friend_id, friend_wx_id=friend_wx_id,
                            friend_nick=friend_nick,
                            status="no_chat",
                            is_compliant="non_compliant",
                            error_msg="无聊天记录",
                            created_at=datetime.now(),
                        )
                    else:
                        # 从所有窗口中计算最低跟进次数
                        windows = result.get("windows", [])
                        min_count = min((w.get("count", 0) for w in windows), default=0)
                        record = FollowUpComplianceResult(
                            user_id=user_id,
                            user_wx_id=user_wx_id,
                            friend_id=friend_id,
                            friend_wx_id=friend_wx_id,
                            friend_nick=friend_nick,
                            is_compliant="compliant" if result.get("is_compliant") else "non_compliant",
                            total_follow_up_days=result.get("total_follow_up_days", 0),
                            chat_date_range=result.get("chat_date_range", ""),
                            window_size_days=60,
                            min_required_count=11,
                            min_window_count=min_count,
                            violation_windows=result.get("violation_windows", []),
                            status="success",
                            created_at=datetime.now(),
                        )
                    session.add(record)
                    saved += 1
                    compliance_status = "合规" if result.get("is_compliant") else "不合规"
                    _log(task_id, f"  [{agent_name}] 检测结果: {compliance_status}", "success")

                elif agent_name == "质检检测":
                    # 保存主表记录（不含大字段）
                    record = QualityCheckResult(
                        user_id=user_id,
                        user_wx_id=user_wx_id,
                        friend_id=friend_id,
                        friend_wx_id=friend_wx_id,
                        friend_nick=friend_nick,
                        check_time_start=result.get("check_time_start"),
                        check_time_end=result.get("check_time_end"),
                        chat_record_count=result.get("chat_record_count"),
                        keyword_detected=result.get("keyword_detected", "no"),
                        detected_keywords=result.get("detected_keywords"),
                        risk_level=result.get("risk_level"),
                        risk_category=result.get("risk_category"),
                        trigger_party=result.get("trigger_party"),
                        risk_description=result.get("risk_description"),
                        status=result.get("status", "success"),
                        created_at=datetime.now(),
                    )
                    session.add(record)
                    session.flush()  # 获取 record.id

                    # 保存详情表记录（大字段）
                    if result.get("keyword_matches") or result.get("key_evidence") or result.get("suggested_action") or result.get("raw_response"):
                        detail = QualityCheckDetail(
                            result_id=record.id,
                            keyword_matches=result.get("keyword_matches"),
                            key_evidence=result.get("key_evidence"),
                            suggested_action=result.get("suggested_action"),
                            raw_response=result.get("raw_response"),
                            created_at=datetime.now(),
                        )
                        session.add(detail)

                    saved += 1
                    risk_level = result.get("risk_level", "none")
                    keyword_status = "检测到关键词" if result.get("keyword_detected") == "yes" else "无风险关键词"
                    _log(task_id, f"  [{agent_name}] {keyword_status}, 风险等级: {risk_level}", "success")

            print(f"[Task {task_id}] 步骤3: 正在 commit...")
            session.commit()
            print(f"[Task {task_id}] 步骤3: commit 完成，耗时 {time.time()-t3:.1f}s")
            _log(task_id, f"分析完成！共保存 {saved} 条记录 (耗时 {time.time()-t3:.1f}s)", "success")

        mark_task_done(task_id)
        print(f"[Task {task_id}] 全部完成！")
        return {"status": "success", "agents": list(results.keys())}

    except Exception as e:
        error_tb = traceback.format_exc()
        _log(task_id, f"分析失败: {e}", "error")
        print(f"[Task {task_id}] 分析失败: {e}")
        print(error_tb)

        mark_task_done(task_id)

        from sqlalchemy.orm import Session
        try:
            with Session(sync_engine) as session:
                ref = _save_referral(
                    user_id, user_wx_id, friend_id, friend_wx_id, friend_nick,
                    "failed", {}, error_msg=str(e),
                )
                session.add(ref)
                session.commit()
        except Exception:
            pass

        if self:
            raise self.retry(exc=e, countdown=60)
        raise e
