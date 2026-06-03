# -*- coding: utf-8 -*-
"""分析结果数据模型 — 拆分为转介绍检测和优秀案例提取两张表"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone

from app.models.database import Base


class ReferralResult(Base):
    """转介绍检测结果表"""
    __tablename__ = "referral_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, comment="销售ID")
    user_wx_id = Column(String(64), nullable=True, comment="销售微信号")
    friend_id = Column(BigInteger, nullable=False, comment="好友ID")
    friend_wx_id = Column(String(64), nullable=True, comment="好友微信号")
    friend_nick = Column(String(128), nullable=True, comment="好友昵称")

    status = Column(String(16), default="success", comment="success / failed")
    result = Column(JSONB, nullable=False, comment="分析结果")
    error_msg = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_wx_id": self.user_wx_id,
            "friend_id": self.friend_id,
            "friend_wx_id": self.friend_wx_id,
            "friend_nick": self.friend_nick,
            "status": self.status,
            "result": self.result,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SalesJourneyResult(Base):
    """优秀成交案例提取结果表 — 销售复盘 / 话术萃取 / 成交拆解"""
    __tablename__ = "sales_journey_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, comment="销售ID")
    user_wx_id = Column(String(64), nullable=True, comment="销售微信号")
    friend_id = Column(BigInteger, nullable=False, comment="好友ID")
    friend_wx_id = Column(String(64), nullable=True, comment="好友微信号")
    friend_nick = Column(String(128), nullable=True, comment="好友昵称/班级名")

    # 6模块分析结果（JSONB存储）
    analysis_result = Column(JSONB, nullable=True, comment="6模块完整分析结果JSON")

    # 快捷检索字段
    deal_time = Column(String(32), nullable=True, comment="成交时间")
    chat_duration = Column(String(32), nullable=True, comment="聊天总时长")
    message_count = Column(Integer, nullable=True, comment="对话轮次")
    sales_style = Column(String(256), nullable=True, comment="销售沟通风格")

    raw_response = Column(Text, nullable=True, comment="AI原始响应")

    status = Column(String(16), default="success", comment="success / failed / no_chat")
    error_msg = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_wx_id": self.user_wx_id,
            "friend_id": self.friend_id,
            "friend_wx_id": self.friend_wx_id,
            "friend_nick": self.friend_nick,
            "analysis_result": self.analysis_result,
            "deal_time": self.deal_time,
            "chat_duration": self.chat_duration,
            "message_count": self.message_count,
            "sales_style": self.sales_style,
            "status": self.status,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CaseExtractionResult(Base):
    """优秀话术提取结果表 — 每条记录一条独立话术（含销售话术 + 唤醒话术）"""
    __tablename__ = "case_extraction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, comment="销售ID")
    user_wx_id = Column(String(64), nullable=True, comment="销售微信号")
    friend_id = Column(BigInteger, nullable=False, comment="好友ID")
    friend_wx_id = Column(String(64), nullable=True, comment="好友微信号")
    friend_nick = Column(String(128), nullable=True, comment="好友昵称")

    # === 话术类型标识 ===
    script_type = Column(String(32), nullable=True, comment="话术类型：销售话术 / 唤醒话术")

    # === 销售话术专属字段（B类）===
    customer_question = Column(Text, nullable=True, comment="客户问题")
    sales_answer = Column(Text, nullable=True, comment="销冠回答")
    customer_intent = Column(String(128), nullable=True, comment="客户意图")

    # === 唤醒话术专属字段（A类）===
    trigger_customer_state = Column(Text, nullable=True, comment="触发客户状态")
    wake_script = Column(Text, nullable=True, comment="销冠唤醒话术原文")
    script_objective = Column(Text, nullable=True, comment="话术核心目标")
    target_audience = Column(Text, nullable=True, comment="适配人群")

    # === 两类话术共享字段 ===
    applicable_scenario = Column(String(256), nullable=True, comment="适用场景")
    tags = Column(String(512), nullable=True, comment="标签（顿号分隔）")
    business_subject = Column(String(128), nullable=True, comment="业务科目")
    compliance_risk = Column(Text, nullable=True, comment="合规风险")
    core_design_logic = Column(Text, nullable=True, comment="核心设计逻辑")
    key_techniques = Column(String(512), nullable=True, comment="话术关键技巧")
    pitfall_avoid = Column(Text, nullable=True, comment="反例避坑")
    customer_profile = Column(Text, nullable=True, comment="客户画像")

    # 原始 AI 响应（备用）
    raw_response = Column(Text, nullable=True, comment="AI原始响应")

    # 批次 summary（JSONB，同批次话术共享）
    summary = Column(JSONB, nullable=True, comment="批次汇总分析（overall_level/top_practices/improvement_suggestions）")

    status = Column(String(16), default="success", comment="success / failed / no_cases")
    error_msg = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_wx_id": self.user_wx_id,
            "friend_id": self.friend_id,
            "friend_wx_id": self.friend_wx_id,
            "friend_nick": self.friend_nick,
            "script_type": self.script_type,
            "customer_question": self.customer_question,
            "sales_answer": self.sales_answer,
            "customer_intent": self.customer_intent,
            "trigger_customer_state": self.trigger_customer_state,
            "wake_script": self.wake_script,
            "script_objective": self.script_objective,
            "target_audience": self.target_audience,
            "applicable_scenario": self.applicable_scenario,
            "tags": self.tags,
            "business_subject": self.business_subject,
            "compliance_risk": self.compliance_risk,
            "core_design_logic": self.core_design_logic,
            "key_techniques": self.key_techniques,
            "pitfall_avoid": self.pitfall_avoid,
            "customer_profile": self.customer_profile,
            "summary": self.summary,
            "status": self.status,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FollowUpComplianceResult(Base):
    """督学跟进合规检测结果表 — 两个月跟进11次标准"""
    __tablename__ = "follow_up_compliance_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, comment="销售ID")
    user_wx_id = Column(String(64), nullable=True, comment="销售微信号")
    friend_id = Column(BigInteger, nullable=False, comment="好友ID")
    friend_wx_id = Column(String(64), nullable=True, comment="好友微信号")
    friend_nick = Column(String(128), nullable=True, comment="好友昵称")

    # 检测结果
    is_compliant = Column(String(16), nullable=False, comment="compliant / non_compliant")
    total_follow_up_days = Column(Integer, nullable=True, comment="总跟进天数（去重后）")
    chat_date_range = Column(String(64), nullable=True, comment="聊天日期范围")
    window_size_days = Column(Integer, default=60, comment="滑动窗口大小（天）")
    min_required_count = Column(Integer, default=11, comment="窗口内最低跟进次数要求")
    min_window_count = Column(Integer, nullable=True, comment="所有窗口中的最低跟进次数")
    violation_windows = Column(JSONB, nullable=True, comment="不合规窗口详情列表")

    raw_response = Column(Text, nullable=True, comment="AI原始响应（备用）")
    status = Column(String(16), default="success", comment="success / failed / no_chat")
    error_msg = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_wx_id": self.user_wx_id,
            "friend_id": self.friend_id,
            "friend_wx_id": self.friend_wx_id,
            "friend_nick": self.friend_nick,
            "is_compliant": self.is_compliant,
            "total_follow_up_days": self.total_follow_up_days,
            "chat_date_range": self.chat_date_range,
            "window_size_days": self.window_size_days,
            "min_required_count": self.min_required_count,
            "min_window_count": self.min_window_count,
            "violation_windows": self.violation_windows,
            "status": self.status,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RiskKeyword(Base):
    """风险关键词配置表"""
    __tablename__ = "risk_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(64), nullable=False, unique=True, comment="关键词")
    category = Column(String(32), nullable=False, comment="类别：refund/complaint/order_cancel/regulatory/fraud")
    severity = Column(String(16), default="medium", comment="严重程度：high/medium/low")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(), comment="更新时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "category": self.category,
            "severity": self.severity,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QualityCheckResult(Base):
    """质检检测结果表 — 关键词预警 + AI深度分析"""
    __tablename__ = "quality_check_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, comment="销售ID")
    user_name = Column(String(64), nullable=True, comment="销售姓名")
    user_wx_id = Column(String(64), nullable=True, comment="销售微信号")
    friend_id = Column(BigInteger, nullable=False, comment="好友ID")
    friend_name = Column(String(128), nullable=True, comment="好友姓名")
    friend_wx_id = Column(String(64), nullable=True, comment="好友微信号")
    friend_nick = Column(String(128), nullable=True, comment="好友昵称")
    chat_title = Column(String(256), nullable=True, comment="好友备注")
    alias = Column(String(128), nullable=True, comment="好友别名")
    phone = Column(String(32), nullable=True, comment="绑定手机号")
    remark_phone = Column(String(32), nullable=True, comment="备注手机号")

    # === 时间范围 ===
    check_time_start = Column(String(32), nullable=True, comment="检测起始时间")
    check_time_end = Column(String(32), nullable=True, comment="检测结束时间")
    chat_record_count = Column(Integer, nullable=True, comment="聊天记录条数")

    # === 关键词检测结果 ===
    keyword_detected = Column(String(16), default="no", comment="yes/no 是否检测到关键词")
    detected_keywords = Column(String(512), nullable=True, comment="检测到的关键词列表（逗号分隔）")
    keyword_matches = Column(JSONB, nullable=True, comment="关键词匹配详情：[{keyword, message, time, speaker}]")

    # === AI深度分析结果 ===
    risk_level = Column(String(16), nullable=True, comment="风险等级：high/medium/low/none")
    risk_category = Column(String(64), nullable=True, comment="风险类别：投诉/退款/退费/取消订单等")
    risk_description = Column(Text, nullable=True, comment="风险描述")
    suggested_action = Column(Text, nullable=True, comment="建议处理措施")
    key_evidence = Column(JSONB, nullable=True, comment="关键证据：[{content, time, speaker}]")

    # === 原始数据 ===
    raw_response = Column(Text, nullable=True, comment="AI原始响应")

    # === 状态 ===
    status = Column(String(16), default="success", comment="success/failed/no_chat/no_keyword")
    error_msg = Column(Text, nullable=True, comment="失败原因")
    batch_task_id = Column(String(64), nullable=True, comment="批量任务ID")
    trigger_party = Column(String(16), nullable=True, comment="触发方：sales/customer/both")

    # === 人工修正字段 ===
    remark = Column(Text, nullable=True, comment="质检备注")
    modified_risk_level = Column(String(16), nullable=True, comment="人工修正的风险等级")
    modified_at = Column(DateTime, nullable=True, comment="最后修改时间")
    modified_by = Column(String(64), nullable=True, comment="最后修改人ID")
    modified_by_name = Column(String(64), nullable=True, comment="最后修改人姓名")

    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_wx_id": self.user_wx_id,
            "friend_id": self.friend_id,
            "friend_name": self.friend_name,
            "friend_wx_id": self.friend_wx_id,
            "friend_nick": self.friend_nick,
            "chat_title": self.chat_title,
            "alias": self.alias,
            "phone": self.phone,
            "remark_phone": self.remark_phone,
            "check_time_start": self.check_time_start,
            "check_time_end": self.check_time_end,
            "chat_record_count": self.chat_record_count,
            "keyword_detected": self.keyword_detected,
            "detected_keywords": self.detected_keywords,
            "keyword_matches": self.keyword_matches,
            "risk_level": self.risk_level,
            "risk_category": self.risk_category,
            "risk_description": self.risk_description,
            "suggested_action": self.suggested_action,
            "key_evidence": self.key_evidence,
            "raw_response": self.raw_response,
            "status": self.status,
            "error_msg": self.error_msg,
            "batch_task_id": self.batch_task_id,
            "trigger_party": self.trigger_party,
            "remark": self.remark,
            "modified_risk_level": self.modified_risk_level,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "modified_by": self.modified_by,
            "modified_by_name": self.modified_by_name,
            # 显示的风险等级（优先使用修正后的）
            "display_risk_level": self.modified_risk_level or self.risk_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    __table_args__ = (
        Index("ix_quality_check_user_id", "user_id"),
        Index("ix_quality_check_risk_level", "risk_level"),
        Index("ix_quality_check_created_at", "created_at"),
        Index("ix_quality_check_user_created", "user_id", "created_at"),
        Index("ix_quality_check_trigger_party", "trigger_party"),
    )


class RefundWhitelistPattern(Base):
    """协议话术白名单表"""
    __tablename__ = "refund_whitelist_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern = Column(String(100), nullable=False, unique=True, comment="话术内容")
    description = Column(String(200), nullable=True, comment="描述说明")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(), comment="更新时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pattern": self.pattern,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QualityCheckModificationLog(Base):
    """质检结果修改日志表 — 审计追踪"""
    __tablename__ = "quality_check_modification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, nullable=False, comment="质检结果ID")
    user_id = Column(String(64), nullable=False, comment="修改人ID")
    user_name = Column(String(64), nullable=True, comment="修改人姓名")

    # 修改内容
    old_risk_level = Column(String(16), nullable=True, comment="原风险等级")
    new_risk_level = Column(String(16), nullable=True, comment="新风险等级")
    old_remark = Column(Text, nullable=True, comment="原备注")
    new_remark = Column(Text, nullable=True, comment="新备注")

    modified_at = Column(DateTime, default=lambda: datetime.now(), comment="修改时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "result_id": self.result_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "old_risk_level": self.old_risk_level,
            "new_risk_level": self.new_risk_level,
            "old_remark": self.old_remark,
            "new_remark": self.new_remark,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }
