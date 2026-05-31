# -*- coding: utf-8 -*-
"""API 访问日志中间件 — 捕获所有 API 请求并记录"""
import time
import json
import asyncio
import logging
from typing import Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.services.system_log_service import log_service
from app.services.auth import decode_access_token

logger = logging.getLogger(__name__)

# 敏感字段脱敏列表
SENSITIVE_FIELDS = {"password", "password_hash", "token", "access_token", "refresh_token", "secret", "api_key"}

# 不记录日志的路径
EXCLUDED_PATHS = {
    "/api/health",
    "/api/logs",  # 避免日志查询产生循环日志
    "/favicon.ico",
}


def sanitize_dict(data: Optional[dict]) -> Optional[dict]:
    """脱敏字典中的敏感字段"""
    if not data:
        return data
    sanitized = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        else:
            # 截断过长的值
            if isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "..."
            else:
                sanitized[key] = value
    return sanitized


class AccessLogMiddleware(BaseHTTPMiddleware):
    """API访问日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 跳过不需要记录的路径
        if path in EXCLUDED_PATHS or not path.startswith("/api"):
            return await call_next(request)

        # 跳过日志查询相关路径（避免循环）
        if path.startswith("/api/logs") and path != "/api/logs/my-actions":
            return await call_next(request)

        # 记录开始时间
        start_time = time.perf_counter()

        # 提取用户信息 (从JWT)
        user_id: Optional[int] = None
        username: Optional[str] = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_access_token(token)
            if payload:
                user_id = int(payload.get("sub", 0)) if payload.get("sub") else None
                username = payload.get("username")

        # 提取请求信息
        request_method = request.method
        request_query = str(request.query_params)[:500] if request.query_params else None
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:512]

        # 读取请求体 (POST/PUT/PATCH)
        request_body_str: Optional[str] = None
        if request_method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_data = json.loads(body_bytes.decode("utf-8"))
                    sanitized_body = sanitize_dict(body_data)
                    request_body_str = json.dumps(sanitized_body, ensure_ascii=False)[:1000]
            except Exception:
                request_body_str = None

        # 调用下一个处理程序
        response: Response = await call_next(request)

        # 计算响应时间
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        response_status = response.status_code

        # 确定日志级别
        if response_status < 400:
            log_level = "info"
        elif response_status < 500:
            log_level = "warning"
        else:
            log_level = "error"

        # 异步写入日志 (不阻塞响应)
        asyncio.create_task(self._write_access_log(
            log_level=log_level,
            user_id=user_id,
            username=username,
            request_method=request_method,
            request_path=path,
            request_query=request_query,
            request_body=request_body_str,
            response_status=response_status,
            response_time_ms=response_time_ms,
            ip_address=ip_address,
            user_agent=user_agent,
        ))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP (支持代理)"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    async def _write_access_log(self, **kwargs):
        """异步写入访问日志"""
        try:
            await log_service.write_log(log_type="api_access", **kwargs)
        except Exception as e:
            logger.error(f"Failed to write access log: {e}")