# -*- coding: utf-8 -*-
"""开放接口 — 独立 API Key 鉴权，供外部系统调用"""
import json
import logging
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from config import settings
from app.services.system_log_service import log_service

logger = logging.getLogger(__name__)

router = APIRouter()

# API Key 鉴权：通过 X-API-Key 请求头传递
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    return request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")


async def _verify_api_key(request: Request, api_key: str | None = Security(_api_key_header)) -> str:
    """校验请求头中的 API Key 是否与配置一致"""
    if not settings.OPEN_API_KEY:
        raise HTTPException(status_code=503, detail="开放接口未配置，请联系管理员")
    if not api_key or not secrets.compare_digest(api_key, settings.OPEN_API_KEY):
        # 记录鉴权失败日志
        await log_service.write_log(
            log_type="audit",
            log_level="warning",
            request_method=request.method,
            request_path=str(request.url.path),
            response_status=401,
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("User-Agent", "")[:500],
            action="open_api_auth_failed",
            resource_type="open_api",
            extra_data={"provided_key_prefix": api_key[:8] + "..." if api_key and len(api_key) > 8 else api_key},
            immediate=True,
        )
        raise HTTPException(status_code=401, detail="API Key 无效")
    return api_key


# ── 请求 / 响应模型 ──────────────────────────────

class OpenApiRequest(BaseModel):
    """开放接口入参 — 调用方传入任意 JSON 内容"""
    data: Any  # 任意 JSON 结构


class OpenApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


# ── 接口 ──────────────────────────────────────────

@router.post("/callLog", response_model=OpenApiResponse)
async def echo(
    req: OpenApiRequest,
    request: Request,
    _api_key: str = Security(_verify_api_key),
):
    """回显接口 — 将传入的 data 原样返回，用于联调验证"""
    start_time = time.time()
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    logger.info(f"[OpenAPI] callLog 被调用, ip={ip_address}, data_type={type(req.data).__name__}")

    try:
        response = OpenApiResponse(data={})
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 记录成功调用日志
        await log_service.write_log(
            log_type="api_access",
            log_level="info",
            request_method="POST",
            request_path="/open-api/callLog",
            request_body=json.dumps(req.data, ensure_ascii=False)[:2000],
            response_status=200,
            response_time_ms=elapsed_ms,
            ip_address=ip_address,
            user_agent=user_agent[:500],
            action="open_api_call",
            resource_type="open_api",
            resource_id="callLog",
            extra_data={"data_type": type(req.data).__name__},
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
            request_body=json.dumps(req.data, ensure_ascii=False)[:2000],
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
