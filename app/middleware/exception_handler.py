# -*- coding: utf-8 -*-
"""全局异常处理中间件 — 捕获未处理的异常并记录到日志"""
import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.system_log_service import log_service
from app.services.auth import decode_access_token

logger = logging.getLogger(__name__)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件"""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            # 获取用户信息
            user_id = None
            username = None

            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                payload = decode_access_token(token)
                if payload:
                    user_id = int(payload.get("sub", 0)) if payload.get("sub") else None
                    username = payload.get("username")

            # 获取客户端IP
            forwarded = request.headers.get("X-Forwarded-For")
            ip_address = forwarded.split(",")[0].strip() if forwarded else (
                request.headers.get("X-Real-IP") or
                (request.client.host if request.client else "unknown")
            )

            # 记录错误日志（立即写入）
            await log_service.write_log(
                log_type="error",
                log_level="error",
                user_id=user_id,
                username=username,
                request_method=request.method,
                request_path=request.url.path,
                ip_address=ip_address,
                error_type=type(e).__name__,
                error_message=str(e),
                error_stacktrace=traceback.format_exc(),
                immediate=True,
            )

            # 记录到控制台
            logger.exception(f"Unhandled exception: {e}")

            # 返回错误响应
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error", "error": str(e)},
            )