# -*- coding: utf-8 -*-
"""开放接口 — 独立 API Key 鉴权，供外部系统调用"""
import json
import logging
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Security
# from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from config import settings
from app.models.database import async_session
from app.models.result import CallLogRecord
from app.services.system_log_service import log_service
from app.tasks.dingtalk_sync import sync_call_log_to_dingtalk

logger = logging.getLogger(__name__)

router = APIRouter()

# API Key 鉴权：通过 X-API-Key 请求头传递
# _api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
#
#
def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    return request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
#
#
# async def _verify_api_key(request: Request, api_key: str | None = Security(_api_key_header)) -> str:
#     """校验请求头中的 API Key 是否与配置一致"""
#     if not settings.OPEN_API_KEY:
#         raise HTTPException(status_code=503, detail="开放接口未配置，请联系管理员")
#     if not api_key or not secrets.compare_digest(api_key, settings.OPEN_API_KEY):
#         # 记录鉴权失败日志
#         await log_service.write_log(
#             log_type="audit",
#             log_level="warning",
#             request_method=request.method,
#             request_path=str(request.url.path),
#             response_status=401,
#             ip_address=_get_client_ip(request),
#             user_agent=request.headers.get("User-Agent", "")[:500],
#             action="open_api_auth_failed",
#             resource_type="open_api",
#             extra_data={"provided_key_prefix": api_key[:8] + "..." if api_key and len(api_key) > 8 else api_key},
#             immediate=True,
#         )
#         raise HTTPException(status_code=401, detail="API Key 无效")
#     return api_key


# ── 请求 / 响应模型 ──────────────────────────────

# class OpenApiRequest(BaseModel):
#     """开放接口入参 — 调用方传入任意 JSON 内容"""
#     data: Any  # 任意 JSON 结构
#     model_config = {
#         "extra": "allow"
#     }

class OpenApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


# ── 接口 ──────────────────────────────────────────

@router.post("/callLog", response_model=OpenApiResponse)
async def echo(
    # req: OpenApiRequest,
    request: Request,
    # _api_key: str = Security(_verify_api_key),
):
    """回显接口 — 将传入的 data 原样返回，用于联调验证。同时入库并同步钉钉表格"""
    start_time = time.time()
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    logger.info(f"[OpenAPI] callLog 被调用, ip={ip_address}")

    try:
        # 读取客户端完整 JSON 请求体（整段报文，包含外层 data 结构）
        full_raw_body = await request.json()
        # 序列化为字符串，保留中文，限制长度避免日志过大（沿用原有2000字符截断规则）
        full_request_body = json.dumps(full_raw_body, ensure_ascii=False)[:2000]
    except Exception:
        # 兼容非标准JSON、空请求体等异常场景
        full_request_body = ""
        full_raw_body = {}

    # === 解析数据 ===
    phone = None
    call_link = None
    complaint_content = None

    try:
        body = full_raw_body
        # 提取手机号
        if "text" in body and isinstance(body["text"], dict):
            phone = body["text"].get("手机号")
            call_link = body["text"].get("通话链接")

        # 提取投诉内容（通过 custom_fields_map 反查）
        if "custom_fields_map" in body and "data" in body:
            custom_fields_map = body.get("custom_fields_map", {})
            data_section = body.get("data", {})
            # 遍历 custom_fields_map 找到值为 "投诉内容" 的 UUID
            for uuid_key, field_name in custom_fields_map.items():
                if field_name == "投诉内容":
                    complaint_content = data_section.get(uuid_key)
                    break

    except Exception as e:
        logger.warning(f"[OpenAPI] callLog 数据解析失败: {e}")

    # === 入库 ===
    record = None
    try:
        async with async_session() as session:
            record = CallLogRecord(
                phone=phone,
                call_link=call_link,
                complaint_content=complaint_content,
                synced_to_dingtalk=False,
                raw_body=full_raw_body if isinstance(full_raw_body, dict) else None,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            logger.info(f"[OpenAPI] callLog 入库成功: id={record.id}, phone={phone}")
    except Exception as e:
        logger.error(f"[OpenAPI] callLog 入库失败: {e}")
        # 入库失败不影响接口响应，继续执行

    # === 派发钉钉同步异步任务 ===
    dingtalk_dispatched = False
    if record:
        try:
            sync_call_log_to_dingtalk.delay(record.id)
            dingtalk_dispatched = True
            logger.info(f"[OpenAPI] callLog 钉钉同步任务已派发: record_id={record.id}")
        except Exception as e:
            logger.error(f"[OpenAPI] callLog 钉钉任务派发失败: {e}")

    try:
        response = OpenApiResponse(data={})
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 记录成功调用日志
        await log_service.write_log(
            log_type="api_access",
            log_level="info",
            request_method="POST",
            request_path="/open-api/callLog",
            request_body=full_request_body,
            response_status=200,
            response_time_ms=elapsed_ms,
            ip_address=ip_address,
            user_agent=user_agent[:500],
            action="open_api_call",
            resource_type="open_api",
            resource_id="callLog",
            extra_data={
                "phone": phone,
                "call_link": call_link,
                "complaint_content": complaint_content,
                "dingtalk_task_dispatched": dingtalk_dispatched,
            },
        )

        return response

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 记录异常日志
        await log_service.write_log(
            log_type="error",
            log_level="error",
            request_method="POST",
            request_path="/open-api/callLog",
            request_body=full_request_body,
            response_status=500,
            response_time_ms=elapsed_ms,
            ip_address=ip_address,
            user_agent=user_agent[:500],
            error_type=type(e).__name__,
            error_message=str(e),
            action="open_api_call",
            resource_type="open_api",
            resource_id="callLog",
            immediate=True,
        )
        raise
