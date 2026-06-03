# -*- coding: utf-8 -*-
"""Fun-ASR 语音转文字底层服务

职责:
    直接与 DashScope (阿里云) ASR 服务通信
    负责 HTTP 请求、任务提交、状态轮询、结果下载

架构位置:
    底层服务，被 VoiceTranscriptionService 调用
    不直接暴露给业务层使用

调用链:
    质检模块 -> VoiceTranscriptionService -> ASRService -> DashScope

用法:
    # 通常不直接调用，通过 VoiceTranscriptionService 使用
    from app.services.asr_service import transcribe_voice
    text = transcribe_voice("https://.../voice.mp3")

配置依赖:
    ASR_BASE_URL, ASR_SUBMIT_PATH, ASR_QUERY_PATH
    DASHSCOPE_API_KEY, ASR_MODEL, ASR_TIMEOUT, etc.
"""
import time
import requests
from config import settings

# 使用配置中的ASR服务URL
ASR_SUBMIT_URL = f"{settings.ASR_BASE_URL}{settings.ASR_SUBMIT_PATH}"
ASR_QUERY_URL = f"{settings.ASR_BASE_URL}{settings.ASR_QUERY_PATH}"


def transcribe_voice(voice_url: str, language_hints: list = None) -> str:
    """
    语音转文字（Fun-ASR异步调用）

    流程:
        1. 提交转写任务到 DashScope
        2. 轮询等待任务完成（最多60次，间隔2秒）
        3. 下载并解析转写结果

    Args:
        voice_url: 语音文件URL（公网可访问）
        language_hints: 语言提示，如 ["zh", "en"]

    Returns:
        转写后的纯文本

    Raises:
        Exception: ASR任务失败
        TimeoutError: 轮询超时（约120秒）
    """
    # 1. 提交转写任务
    task_id = _submit_transcription_task(voice_url, language_hints)

    # 2. 轮询等待任务完成
    result = _poll_task_result(task_id)

    # 3. 下载并解析结果
    text = _download_transcription(result["transcription_url"])

    return text


def _submit_transcription_task(voice_url: str, language_hints: list = None) -> str:
    """提交转写任务，返回task_id"""
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }

    payload = {
        "model": settings.ASR_MODEL,
        "input": {
            "file_urls": [voice_url]
        },
        "parameters": {
            "channel_id": [settings.ASR_CHANNEL_ID],
            "language_hints": language_hints or [settings.ASR_DEFAULT_LANGUAGE]
        }
    }

    resp = requests.post(ASR_SUBMIT_URL, headers=headers, json=payload, timeout=settings.ASR_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    return data["output"]["task_id"]


def _poll_task_result(task_id: str) -> dict:
    """轮询任务状态，直到完成或超时"""
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "X-DashScope-Async": "enable"
    }

    for _ in range(settings.ASR_MAX_RETRIES):
        resp = requests.get(f"{ASR_QUERY_URL}/{task_id}", headers=headers, timeout=settings.ASR_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        status = data["output"]["task_status"]
        if status == "SUCCEEDED":
            return data["output"]["results"][0]  # 返回第一个文件的结果
        elif status in ("FAILED", "UNKNOWN"):
            raise Exception(f"ASR任务失败: {data}")

        time.sleep(settings.ASR_POLL_INTERVAL)

    raise TimeoutError("ASR任务超时")


def _download_transcription(transcription_url: str) -> str:
    """从URL下载转写结果，提取文本"""
    resp = requests.get(transcription_url, timeout=settings.ASR_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    # 提取完整文本
    transcripts = data.get("transcripts", [])
    if not transcripts:
        return ""

    # 合并所有通道的文本
    texts = []
    for t in transcripts:
        text = t.get("text", "")
        if text:
            texts.append(text)

    return " ".join(texts)
