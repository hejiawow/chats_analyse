# -*- coding: utf-8 -*-
"""钉钉在线文档表格 API 服务封装"""

import logging
import time
import httpx

from config import settings

logger = logging.getLogger(__name__)

# 钉钉文档 API 基础 URL（新版）
DINGTALK_DOC_API_BASE = "https://api.dingtalk.com/v1.0/doc"

# Access Token 缓存（简单内存缓存）
_access_token_cache = {"token": None, "expire_at": 0}


async def get_access_token() -> str | None:
    """获取钉钉 access_token（带缓存）

    Returns:
        access_token 字符串，失败返回 None
    """
    # 检查缓存是否有效
    if _access_token_cache["token"] and _access_token_cache["expire_at"] > time.time():
        return _access_token_cache["token"]

    # 未配置凭证，直接返回 None
    if not settings.DINGTALK_APP_KEY or not settings.DINGTALK_APP_SECRET:
        logger.warning("[钉钉] 未配置 DINGTALK_APP_KEY 或 DINGTALK_APP_SECRET，跳过同步")
        return None

    # 请求新的 access_token（企业内部应用使用 appkey + appsecret）
    url = "https://oapi.dingtalk.com/gettoken"
    params = {
        "appkey": settings.DINGTALK_APP_KEY,
        "appsecret": settings.DINGTALK_APP_SECRET,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()

            if result.get("errcode") == 0:
                token = result.get("access_token")
                expires_in = result.get("expires_in", 7200) - 60  # 提前60秒过期
                _access_token_cache["token"] = token
                _access_token_cache["expire_at"] = time.time() + expires_in
                logger.info(f"[钉钉] access_token 获取成功，有效期 {expires_in} 秒")
                return token
            else:
                logger.error(f"[钉钉] access_token 获取失败: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}")
                return None

    except Exception as e:
        logger.error(f"[钉钉] access_token 请求异常: {e}")
        return None


async def append_row_to_sheet(values: list) -> tuple[bool, str | None]:
    """向钉钉在线文档表格追加一行数据

    Args:
        values: 行数据列表，例如 ["手机号", "通话链接", "投诉内容", "时间"]

    Returns:
        (success, error_message): 成功返回 (True, None)，失败返回 (False, 错误信息)
    """
    # 检查配置
    if not settings.DINGTALK_WORKBOOK_ID or not settings.DINGTALK_SHEET_ID:
        logger.warning("[钉钉] 未配置 DINGTALK_WORKBOOK_ID 或 DINGTALK_SHEET_ID，跳过同步")
        return False, "未配置钉钉表格参数"

    # 获取 access_token
    token = await get_access_token()
    if not token:
        return False, "access_token 获取失败"

    if not settings.DINGTALK_OPERATOR_UNION_ID:
        return False, "未配置 DINGTALK_OPERATOR_UNION_ID"

    headers = {
        "x-acs-dingtalk-access-token": token,
        "Content-Type": "application/json",
    }

    if not values:
        return False, "无数据需要同步"

    # 正确的钉钉文档表格追加行 API
    url = (
        f"https://api.dingtalk.com/v1.0/doc/workbooks/{settings.DINGTALK_WORKBOOK_ID}"
        f"/sheets/{settings.DINGTALK_SHEET_ID}/appendRows"
        f"?operatorId={settings.DINGTALK_OPERATOR_UNION_ID}"
    )
    body = {"values": [values]}

    logger.info(f"[钉钉] 追加行数据: url={url}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=headers, json=body)

            logger.info(
                f"[钉钉] API响应: status={response.status_code}, "
                f"body={response.text[:300] if response.text else 'empty'}"
            )

            if response.status_code in (200, 201):
                logger.info(f"[钉钉] 表格追加成功: {values}")
                return True, None
            else:
                error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                return False, f"HTTP {response.status_code}: {error_msg}"

    except httpx.HTTPStatusError as e:
        logger.warning(f"[钉钉] API失败: HTTP {e.response.status_code}")
        return False, f"HTTP {e.response.status_code}"
    except Exception as e:
        logger.warning(f"[钉钉] API异常: {e}")
        return False, str(e)


def invalidate_token_cache():
    """清空 access_token 缓存"""
    _access_token_cache["token"] = None
    _access_token_cache["expire_at"] = 0