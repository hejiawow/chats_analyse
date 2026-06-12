# -*- coding: utf-8 -*-
"""钉钉表格同步任务 — 将通话记录异步追加到钉钉在线表格"""
import logging

import httpx
from sqlalchemy import update

from app.celery_app import celery_app
from app.models.database import SessionLocal
from app.models.result import CallLogRecord
from config import settings

logger = logging.getLogger(__name__)

# 钉钉 API 常量
DINGTALK_TOKEN_URL = "https://oapi.dingtalk.com/gettoken"
DINGTALK_APPEND_URL_TPL = (
    "https://api.dingtalk.com/v1.0/doc/workbooks/{workbook_id}"
    "/sheets/{sheet_id}/appendRows?operatorId={operator_id}"
)


def _get_access_token_sync() -> str | None:
    """同步获取钉钉 access_token（Celery Worker 中使用）"""
    if not settings.DINGTALK_APP_KEY or not settings.DINGTALK_APP_SECRET:
        logger.warning("[钉钉] 未配置 APP_KEY / APP_SECRET，跳过")
        return None

    try:
        resp = httpx.get(
            DINGTALK_TOKEN_URL,
            params={"appkey": settings.DINGTALK_APP_KEY, "appsecret": settings.DINGTALK_APP_SECRET},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("errcode") == 0:
            return result.get("access_token")
        logger.error("[钉钉] token 获取失败: %s", result.get("errmsg"))
    except Exception as e:
        logger.error("[钉钉] token 请求异常: %s", e)
    return None


@celery_app.task(
    name="app.tasks.dingtalk_sync.sync_call_log_to_dingtalk",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def sync_call_log_to_dingtalk(self, record_id: int):
    """将指定 call_log_records 记录同步到钉钉表格

    Args:
        record_id: CallLogRecord 主键 ID
    """
    session = SessionLocal()
    try:
        record = session.get(CallLogRecord, record_id)
        if not record:
            logger.warning("[钉钉同步] record_id=%s 不存在，跳过", record_id)
            return {"status": "skipped", "reason": "record not found"}

        # 构造行数据（与表格列顺序一致）
        row_values = [
            record.phone or "",
            record.call_link or "",
            record.complaint_content or "",
            record.request_time.strftime("%Y-%m-%d %H:%M:%S") if record.request_time else "",
        ]

        # 获取 access_token
        token = _get_access_token_sync()
        if not token:
            raise RuntimeError("钉钉 access_token 获取失败")

        # 调用追加行 API
        url = DINGTALK_APPEND_URL_TPL.format(
            workbook_id=settings.DINGTALK_WORKBOOK_ID,
            sheet_id=settings.DINGTALK_SHEET_ID,
            operator_id=settings.DINGTALK_OPERATOR_UNION_ID,
        )
        headers = {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json",
        }

        resp = httpx.post(url, headers=headers, json={"values": [row_values]}, timeout=15)

        if resp.status_code in (200, 201):
            # 标记同步成功
            session.execute(
                update(CallLogRecord)
                .where(CallLogRecord.id == record_id)
                .values(synced_to_dingtalk=True, dingtalk_sync_error=None)
            )
            session.commit()
            logger.info("[钉钉同步] 成功: record_id=%s", record_id)
            return {"status": "ok", "record_id": record_id}
        else:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            raise RuntimeError(error_msg)

    except Exception as exc:
        session.rollback()
        # 记录失败原因
        try:
            session.execute(
                update(CallLogRecord)
                .where(CallLogRecord.id == record_id)
                .values(dingtalk_sync_error=str(exc))
            )
            session.commit()
        except Exception:
            session.rollback()

        # 自动重试（指数退避）
        logger.warning("[钉钉同步] 失败 record_id=%s, 准备重试: %s", record_id, exc)
        raise self.retry(exc=exc)

    finally:
        session.close()
