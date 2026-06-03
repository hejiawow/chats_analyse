# -*- coding: utf-8 -*-
"""语音转写 Celery 任务 - 后台处理"""
import time
from datetime import datetime
from app.celery_app import celery_app
from app.services.voice_transcription_service import voice_service
from app.services.asr_service import transcribe_voice


@celery_app.task(bind=True, name="app.tasks.voice_transcription.process_task", max_retries=3)
def process_task(self, task_id: str):
    """
    处理单条语音转写任务

    输入: task_id
    处理: 调用ASR转写，更新数据库状态
    """
    from app.models.database import sync_engine
    from app.models.voice_task import VoiceTranscriptionTask
    from sqlalchemy.orm import Session

    try:
        # 获取任务信息
        with Session(sync_engine) as session:
            task = session.query(VoiceTranscriptionTask).filter_by(task_id=task_id).first()
            if not task:
                return {"status": "error", "message": "任务不存在"}

            mp3_url = task.mp3_url

            # 更新为运行中
            task.status = "running"
            task.started_at = datetime.now()
            session.commit()

        # 调用ASR转写
        start_time = time.time()
        try:
            text = transcribe_voice(mp3_url)
            processing_time = time.time() - start_time

            # 更新成功状态
            voice_service.update_task_status(
                task_id=task_id,
                status="success",
                result_text=text
            )

            return {
                "status": "success",
                "task_id": task_id,
                "text": text,
                "processing_time": processing_time
            }

        except Exception as e:
            # 更新失败状态
            voice_service.update_task_status(
                task_id=task_id,
                status="failed",
                error_msg=str(e)
            )

            # 重试
            raise self.retry(exc=e, countdown=60)

    except Exception as e:
        return {"status": "error", "task_id": task_id, "error": str(e)}


@celery_app.task(bind=True, name="app.tasks.voice_transcription.process_batch", max_retries=3)
def process_batch(self, batch_id: str):
    """
    处理批量语音转写任务

    输入: batch_id
    处理: 批量调用ASR，更新所有子任务状态
    """
    from app.models.database import sync_engine
    from app.models.voice_task import VoiceTranscriptionBatch, VoiceTranscriptionTask
    from sqlalchemy.orm import Session

    try:
        with Session(sync_engine) as session:
            # 获取批次信息
            batch = session.query(VoiceTranscriptionBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                return {"status": "error", "message": "批次不存在"}

            # 更新批次为运行中
            batch.status = "running"
            batch.started_at = datetime.now()
            session.commit()

            # 获取所有pending的子任务
            tasks = session.query(VoiceTranscriptionTask).filter_by(
                batch_id=batch_id,
                status="pending"
            ).all()

            if not tasks:
                return {"status": "success", "message": "没有待处理任务"}

            # 批量处理
            results = []
            for task in tasks:
                try:
                    # 更新为运行中
                    task.status = "running"
                    session.commit()

                    # 调用ASR
                    text = transcribe_voice(task.mp3_url)

                    # 更新成功
                    task.status = "success"
                    task.result_text = text
                    task.completed_at = datetime.now()
                    session.commit()

                    results.append({
                        "task_id": task.task_id,
                        "status": "success",
                        "text": text
                    })

                except Exception as e:
                    # 更新失败
                    task.status = "failed"
                    task.error_msg = str(e)
                    task.retry_count += 1
                    task.completed_at = datetime.now()
                    session.commit()

                    results.append({
                        "task_id": task.task_id,
                        "status": "failed",
                        "error": str(e)
                    })

            # 更新批次统计
            voice_service._update_batch_stats(batch_id)

            return {
                "status": "success",
                "batch_id": batch_id,
                "processed": len(results),
                "results": results
            }

    except Exception as e:
        return {"status": "error", "batch_id": batch_id, "error": str(e)}
