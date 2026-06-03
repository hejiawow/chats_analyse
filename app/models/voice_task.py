# -*- coding: utf-8 -*-
"""语音转写任务数据模型 - 双表设计"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Index
from app.models.database import Base


class VoiceTranscriptionBatch(Base):
    """语音转写批次任务 - 记录整体状态和进度"""
    __tablename__ = "voice_transcription_batches"

    id = Column(Integer, primary_key=True)
    batch_id = Column(String(64), unique=True, index=True, nullable=False)

    # 输入信息
    total_count = Column(Integer, default=0)
    source_type = Column(String(32))
    source_id = Column(String(64))

    # 进度统计（实时更新）
    completed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    pending_count = Column(Integer, default=0)
    running_count = Column(Integer, default=0)

    # 整体状态
    status = Column(String(16), default="pending")

    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_batch_status", "status"),
        Index("ix_batch_source", "source_type", "source_id"),
    )

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "total_count": self.total_count,
            "completed_count": self.completed_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class VoiceTranscriptionTask(Base):
    """语音转写子任务 - 记录每条语音的详细处理信息"""
    __tablename__ = "voice_transcription_tasks"

    id = Column(Integer, primary_key=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False)
    batch_id = Column(String(64), index=True, nullable=True)

    # 输入
    mp3_url = Column(String(512), nullable=False)

    # 输出
    result_text = Column(Text, nullable=True)
    status = Column(String(16), default="pending")
    error_msg = Column(Text, nullable=True)

    # 统计
    retry_count = Column(Integer, default=0)
    processing_time = Column(Float, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_task_batch", "batch_id"),
        Index("ix_task_status", "status"),
        Index("ix_task_url", "mp3_url"),
    )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "batch_id": self.batch_id,
            "mp3_url": self.mp3_url,
            "result_text": self.result_text,
            "status": self.status,
            "error_msg": self.error_msg,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
