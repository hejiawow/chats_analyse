# -*- coding: utf-8 -*-
"""优秀话术知识库模型 — pgvector 向量列 + HNSW 索引"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime

from app.models.database import Base


class CaseScriptLibrary(Base):
    """话术知识库表 — 每条记录一个高分案例，含 embedding 向量"""
    __tablename__ = "case_script_library"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_case_id = Column(Integer, nullable=True, comment="关联原始 case_extraction_results.id")
    user_id = Column(String(64), nullable=False, comment="销售ID")
    user_wx_id = Column(String(64), nullable=True, comment="销售微信号")
    friend_id = Column(BigInteger, nullable=False, comment="好友ID")
    friend_wx_id = Column(String(64), nullable=True, comment="好友微信号")
    friend_nick = Column(String(128), nullable=True, comment="好友昵称")

    # 筛选标签
    scenario_type = Column(String(128), nullable=True, comment="场景类型")
    customer_type = Column(String(64), nullable=True, comment="客户类型判断")
    communication_stage = Column(String(64), nullable=True, comment="当前沟通阶段")

    # 核心内容
    sales_quote = Column(Text, nullable=True, comment="销售原话")
    comprehensive_review = Column(Text, nullable=True, comment="综合点评")
    customer_profile = Column(Text, nullable=True, comment="客户画像")

    # Embedding 相关 — pgvector Vector(1024) 列
    document_text = Column(Text, nullable=False, comment="被 embedding 的完整文本")
    embedding = Column(Vector(1024), nullable=True, comment="向量嵌入 (pgvector)")

    status = Column(String(16), default="active", comment="active / archived")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")

    __table_args__ = (
        # HNSW 索引 — 余弦向量距离检索
        Index(
            "ix_script_lib_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_case_id": self.source_case_id,
            "user_id": self.user_id,
            "user_wx_id": self.user_wx_id,
            "friend_id": self.friend_id,
            "friend_wx_id": self.friend_wx_id,
            "friend_nick": self.friend_nick,
            "scenario_type": self.scenario_type,
            "customer_type": self.customer_type,
            "communication_stage": self.communication_stage,
            "sales_quote": self.sales_quote,
            "comprehensive_review": self.comprehensive_review,
            "customer_profile": self.customer_profile,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_source(self) -> dict:
        """RAG 返回时作为引用来源的简化格式"""
        return {
            "id": self.id,
            "scenario_type": self.scenario_type,
            "sales_quote": self.sales_quote,
            "communication_stage": self.communication_stage,
            "comprehensive_review": self.comprehensive_review,
            "customer_profile": self.customer_profile,
        }
