# -*- coding: utf-8 -*-
"""语音转文字服务 - 输入 MP3 URL → 输出文字"""
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Tuple

from sqlalchemy.orm import Session
from app.models.database import sync_engine
from app.models.voice_task import VoiceTranscriptionBatch, VoiceTranscriptionTask
from app.services.asr_service import transcribe_voice
from config import settings


class VoiceTranscriptionService:
    """语音转文字服务"""

    MAX_WORKERS = settings.ASR_MAX_WORKERS  # 批量并发数（从配置读取，默认5）
    MAX_RETRY = 3    # 最大重试次数

    # ========== 同步 API ==========

    def transcribe(self, mp3_url: str) -> str:
        """
        同步转写单条 MP3

        输入: MP3 URL (str)
        输出: 文字 (str)
        异常: 转写失败时抛出异常
        """
        return self._transcribe_with_retry(mp3_url)

    def transcribe_batch(self, mp3_urls: List[str]) -> List[Dict]:
        """
        同步批量转写 MP3

        输入: MP3 URL 列表 (list[str])
        输出: 结果列表 (list[dict])
              [
                  {"url": "url1", "text": "文字1", "success": True},
                  {"url": "url2", "text": "文字2", "success": True},
                  {"url": "url3", "text": None, "success": False, "error": "..."}
              ]
        """
        if not mp3_urls:
            return []

        results = []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(self._transcribe_with_retry, url): url
                for url in mp3_urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    text = future.result(timeout=120)
                    results.append({
                        "url": url,
                        "text": text,
                        "success": True
                    })
                except Exception as e:
                    results.append({
                        "url": url,
                        "text": None,
                        "success": False,
                        "error": str(e)
                    })

        return results

    def transcribe_chat_records(self, chat_records: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        转写聊天记录中的语音消息

        输入: chat_records（包含 content_type=34 的语音消息）
        输出: (处理后的records, 统计信息)
        """
        # 1. 提取所有语音URL
        voice_items = []  # [(index, url), ...]
        for idx, record in enumerate(chat_records):
            if record.get("content_type") == 34:
                url = record.get("sentence", "")
                if url:
                    voice_items.append((idx, url))

        if not voice_items:
            return chat_records, {"total_voice": 0, "success": 0, "failed": 0}

        # 2. 批量转写
        urls = [item[1] for item in voice_items]
        results = self.transcribe_batch(urls)

        # 3. 构建 URL -> 文字 映射
        url_to_text = {}
        for r in results:
            if r["success"]:
                url_to_text[r["url"]] = r["text"]
            else:
                url_to_text[r["url"]] = "[语音转写失败]"

        # 4. 替换聊天记录中的语音URL为文字
        processed = [r.copy() for r in chat_records]
        for idx, url in voice_items:
            processed[idx]["sentence"] = url_to_text.get(url, "[语音转写失败]")
            processed[idx]["_voice_url"] = url  # 保留原URL备用

        # 5. 统计
        success_count = sum(1 for r in results if r["success"])
        stats = {
            "total_voice": len(voice_items),
            "success": success_count,
            "failed": len(voice_items) - success_count
        }

        return processed, stats

    # ========== 异步 API ==========

    def submit_task(self, mp3_url: str, source_type: str = None, source_id: str = None) -> str:
        """
        提交异步转写任务

        输入: MP3 URL (str)
        输出: 任务ID (str)
        """
        task_id = f"vt_{uuid.uuid4().hex[:12]}"

        with Session(sync_engine) as session:
            task = VoiceTranscriptionTask(
                task_id=task_id,
                mp3_url=mp3_url,
                status="pending",
                source_type=source_type,
                source_id=source_id
            )
            session.add(task)
            session.commit()

        return task_id

    def submit_batch(self, mp3_urls: List[str], source_type: str = None, source_id: str = None) -> str:
        """
        提交批量异步转写任务

        输入: MP3 URL 列表 (list[str])
        输出: 批次ID (str)
        """
        batch_id = f"vb_{uuid.uuid4().hex[:12]}"

        with Session(sync_engine) as session:
            # 创建批次记录
            batch = VoiceTranscriptionBatch(
                batch_id=batch_id,
                total_count=len(mp3_urls),
                pending_count=len(mp3_urls),
                status="pending",
                source_type=source_type,
                source_id=source_id
            )
            session.add(batch)

            # 创建子任务记录
            for url in mp3_urls:
                task_id = f"vt_{uuid.uuid4().hex[:12]}"
                task = VoiceTranscriptionTask(
                    task_id=task_id,
                    batch_id=batch_id,
                    mp3_url=url,
                    status="pending"
                )
                session.add(task)

            session.commit()

        return batch_id

    def get_result(self, task_id: str) -> str:
        """
        查询转写结果

        输入: 任务ID (str)
        输出: 文字 (str) 或 None（处理中/失败）
        """
        with Session(sync_engine) as session:
            task = session.query(VoiceTranscriptionTask).filter_by(task_id=task_id).first()
            if task and task.status == "success":
                return task.result_text
            return None

    def get_batch_progress(self, batch_id: str) -> Dict:
        """
        查询批次进度

        输入: 批次ID (str)
        输出: 进度信息 (dict)
        """
        with Session(sync_engine) as session:
            batch = session.query(VoiceTranscriptionBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                return {"error": "批次不存在"}

            return {
                "batch_id": batch_id,
                "status": batch.status,
                "progress": {
                    "total": batch.total_count,
                    "completed": batch.completed_count,
                    "success": batch.success_count,
                    "failed": batch.failed_count,
                    "pending": batch.pending_count,
                    "running": batch.running_count
                },
                "percentage": round(batch.completed_count / batch.total_count * 100, 1) if batch.total_count > 0 else 0
            }

    def get_batch_results(self, batch_id: str) -> List[Dict]:
        """
        获取批次所有结果

        输入: 批次ID (str)
        输出: 结果列表 (list[dict])
        """
        with Session(sync_engine) as session:
            tasks = session.query(VoiceTranscriptionTask).filter_by(batch_id=batch_id).all()
            return [
                {
                    "task_id": t.task_id,
                    "mp3_url": t.mp3_url,
                    "text": t.result_text,
                    "status": t.status,
                    "error": t.error_msg
                }
                for t in tasks
            ]

    # ========== 内部方法 ==========

    def _transcribe_with_retry(self, mp3_url: str) -> str:
        """带重试的转写"""
        for attempt in range(self.MAX_RETRY):
            try:
                return transcribe_voice(mp3_url)
            except Exception as e:
                if attempt == self.MAX_RETRY - 1:
                    raise
                time.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s

    def update_task_status(self, task_id: str, status: str, result_text: str = None, error_msg: str = None):
        """更新任务状态（供Celery调用）"""
        with Session(sync_engine) as session:
            task = session.query(VoiceTranscriptionTask).filter_by(task_id=task_id).first()
            if task:
                task.status = status
                if result_text is not None:
                    task.result_text = result_text
                if error_msg is not None:
                    task.error_msg = error_msg
                if status in ["success", "failed"]:
                    task.completed_at = datetime.now()
                session.commit()

                # 如果是批量任务，更新批次统计
                if task.batch_id:
                    self._update_batch_stats(task.batch_id)

    def _update_batch_stats(self, batch_id: str):
        """更新批次统计"""
        with Session(sync_engine) as session:
            batch = session.query(VoiceTranscriptionBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                return

            tasks = session.query(VoiceTranscriptionTask).filter_by(batch_id=batch_id).all()

            total = len(tasks)
            success = sum(1 for t in tasks if t.status == "success")
            failed = sum(1 for t in tasks if t.status == "failed")
            completed = success + failed
            pending = sum(1 for t in tasks if t.status == "pending")
            running = sum(1 for t in tasks if t.status == "running")

            batch.total_count = total
            batch.success_count = success
            batch.failed_count = failed
            batch.completed_count = completed
            batch.pending_count = pending
            batch.running_count = running

            # 判断整体状态
            if failed == total and total > 0:
                batch.status = "failed"
            elif success == total:
                batch.status = "success"
            elif completed == total:
                batch.status = "partial_success"
            elif running > 0:
                batch.status = "running"
                if batch.started_at is None:
                    batch.started_at = datetime.now()
            else:
                batch.status = "pending"

            if batch.status in ["success", "partial_success", "failed"]:
                batch.completed_at = datetime.now()

            session.commit()


# 全局服务实例
voice_service = VoiceTranscriptionService()
