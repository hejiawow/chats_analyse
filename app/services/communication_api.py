# -*- coding: utf-8 -*-
"""云客 API 服务封装（新数据源）

对应接口文档：docs/沟通记录接口入参与出参说明.md
- GET /api/communication-records/query
- GET /api/sales-friends/query
"""

import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

import requests
from requests.exceptions import ConnectionError, ConnectTimeout, RequestException

from app.services.cache import cache_get, cache_set
from config import settings

# 缓存过期时间（秒）
_FRIENDS_CACHE_TTL = 21600  # 销售好友列表：6 小时

logger = logging.getLogger(__name__)

# 东八区时区常量
_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _build_signature_headers(params: dict) -> dict:
    """构建 HMAC-SHA256 签名认证请求头

    签名算法：
    1. 将查询参数按 key 字母序排序，拼接为 key=value&key=value 字符串
    2. message = {app_id}{timestamp}{nonce}{sorted_params_string}
    3. signature = HMAC-SHA256(app_secret, message)
    """
    app_id = getattr(settings, "COMMUNICATION_APP_ID", "")
    app_secret = settings.COMMUNICATION_API_KEY

    # 参数按 key 字母序排序并拼接
    sorted_params = sorted(params.items())
    params_string = "&".join(f"{k}={v}" for k, v in sorted_params)

    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())
    message = f"{app_id}{timestamp}{nonce}{params_string}"

    signature = hmac.new(
        app_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "X-App-Id": app_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


class CommApiError(Exception):
    """云客 API 调用错误"""
    pass


_last_error: str | None = None


def get_last_error() -> str | None:
    """获取最近一次 API 调用错误信息"""
    return _last_error


def _request_get(url: str, params: dict, max_retries: int = 3, timeout: int = 30) -> dict | None:
    """带重试的 GET 请求（HMAC-SHA256 签名认证）

    成功返回 data 字段；失败时将错误信息存入 _last_error 并返回 None。
    """
    global _last_error
    _last_error = None
    # 确保所有参数值为字符串（签名和请求都需要）
    str_params = {k: str(v) for k, v in params.items()}
    last_error_msg = ""

    # 记录整体开始时间
    overall_start = time.time()

    for retry in range(max_retries):
        try:
            # 每次重试重新生成签名（timestamp 需要是最新的）
            headers = _build_signature_headers(str_params)
            logger.debug(f"[comm_api] GET {url}, params={str_params}")

            # 记录单次请求开始时间
            request_start = time.time()
            logger.info(f"[comm_api] 开始请求 (retry {retry}): {url.split('/')[-1]}, timeout={timeout}s")

            response = requests.get(
                url, headers=headers, params=str_params, timeout=timeout, verify=False
            )

            # 计算单次请求耗时
            request_elapsed = time.time() - request_start
            logger.info(f"[comm_api] 请求完成: {url.split('/')[-1]}, 耗时={request_elapsed:.2f}s, 状态码={response.status_code}")

            response.raise_for_status()
            result = response.json()
            # 统一响应结构：{code, message, data, traceID}
            if result.get("code") in (0, 200):
                # 计算整体耗时
                overall_elapsed = time.time() - overall_start
                logger.info(f"[comm_api] API调用成功: {url.split('/')[-1]}, 总耗时={overall_elapsed:.2f}s (含{retry}次重试)")
                return result.get("data")
            else:
                last_error_msg = (
                    f"接口返回非成功状态: code={result.get('code')}, "
                    f"message={result.get('message')}"
                )
                logger.warning(f"[comm_api] {last_error_msg}")
                return None
        except (ConnectTimeout, ConnectionError) as e:
            request_elapsed = time.time() - request_start
            last_error_msg = f"网络连接失败: {e}"
            logger.warning(f"[comm_api] GET 请求失败 (retry {retry}): {url.split('/')[-1]}, 耗时={request_elapsed:.2f}s, 错误={e}")
            if retry < max_retries - 1:
                sleep_time = 2 ** retry
                logger.info(f"[comm_api] 等待 {sleep_time}s 后重试...")
                time.sleep(sleep_time)
        except RequestException as e:
            request_elapsed = time.time() - request_start
            last_error_msg = f"请求异常: {e}"
            logger.error(f"[comm_api] GET 请求异常 (retry {retry}): {url.split('/')[-1]}, 耗时={request_elapsed:.2f}s, 错误={e}")
            if retry < max_retries - 1:
                sleep_time = 2 ** retry
                logger.info(f"[comm_api] 等待 {sleep_time}s 后重试...")
                time.sleep(sleep_time)

    # 计算整体耗时
    overall_elapsed = time.time() - overall_start
    logger.error(f"[comm_api] API调用最终失败: {url.split('/')[-1]}, 总耗时={overall_elapsed:.2f}s, 错误={last_error_msg}")

    _last_error = last_error_msg
    return None


# ---------------------------------------------------------------------------
# 销售好友列表
# ---------------------------------------------------------------------------

def get_sales_friends(
    start_time: int = None,
    end_time: int = None,
    org_level: int = 0,
    org_id: int = 0,
) -> list:
    """获取销售好友列表（GET /api/sales-friends/query）

    API 返回嵌套结构（销售维度），此函数展平为好友维度列表。

    Args:
        start_time: 起始时间戳（秒）
        end_time: 结束时间戳（秒）
        org_level: 组织层级（0=全部）
        org_id: 组织 ID（0=全部）

    Returns:
        展平后的销售好友列表，每条包含:
        - salesUserId, salesName, teamId, teamName, orgDesc (销售信息)
        - channel, friendWechatId, friendWechatNo, lastSendTime (好友信息)
    """
    base_url = settings.COMMUNICATION_API_BASE_URL
    url = f"{base_url}/api/sales-friends/query"

    params = {
        "orgLevel": str(org_level),
        "orgId": str(org_id),
    }
    if start_time:
        params["startTime"] = str(start_time)
    if end_time:
        params["endTime"] = str(end_time)

    # 缓存 key
    cache_key = f"comm_friends:{org_level}:{org_id}:{start_time}:{end_time}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.info(f"[comm_api] 销售好友列表命中缓存")
        return cached

    data = _request_get(url, params, timeout=30)
    if data is None:
        return []

    # data 可能是 list 或 dict（包含 list 字段）
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        raw_list = data.get("list", data.get("items", []))
    else:
        raw_list = []

    # 展平嵌套结构：API 返回的是销售维度数组，每个销售下有 friends 数组
    # 需要将每个 friend 展平为一条记录，合并销售信息和好友信息
    flattened = []
    for sales_item in raw_list:
        sales_user_id = sales_item.get("salesUserId")
        sales_name = sales_item.get("salesName")
        team_id = sales_item.get("teamId")
        team_name = sales_item.get("teamName")
        org_desc = sales_item.get("orgDesc")

        friends = sales_item.get("friends", [])
        for friend in friends:
            flattened.append({
                "salesUserId": sales_user_id,
                "salesName": sales_name,
                "teamId": team_id,
                "teamName": team_name,
                "orgDesc": org_desc,
                "channel": friend.get("channel"),
                "friendWechatId": friend.get("friendWechatId"),
                "friendWechatNo": friend.get("friendWechatNo"),
                "lastSendTime": friend.get("lastSendTime"),
            })

    # 写入缓存
    cache_set(cache_key, flattened, ttl=_FRIENDS_CACHE_TTL)
    logger.info(f"[comm_api] 获取到 {len(flattened)} 条销售好友记录")
    return flattened


# ---------------------------------------------------------------------------
# 沟通记录
# ---------------------------------------------------------------------------

def get_communication_records(
    sales_user_id: str,
    customer_wechat_no: str = None,
    start_time: int = None,
    end_time: int = None,
) -> list:
    """获取云客沟通记录（GET /api/communication-records/query）

    API 返回嵌套结构（销售维度），此函数展平为记录维度列表。

    Args:
        sales_user_id: 销售用户 ID（salesUserId）
        customer_wechat_no: 客户微信号（customerWechatNo），可选
        start_time: 起始时间戳（秒），过滤 msgTime
        end_time: 结束时间戳（秒），过滤 msgTime

    Returns:
        展平后的沟通记录列表，每条包含:
        - salesUserId, salesName (销售信息)
        - channel, recordType, msgId, direction, content, msgTime, sortTime 等 (记录信息)
    """
    base_url = settings.COMMUNICATION_API_BASE_URL
    url = f"{base_url}/api/communication-records/query"

    params = {"salesUserId": sales_user_id}
    if customer_wechat_no:
        params["customerWechatNo"] = customer_wechat_no
    if start_time:
        params["startTime"] = str(start_time)
    if end_time:
        params["endTime"] = str(end_time)

    data = _request_get(url, params, timeout=60)
    if data is None:
        return []

    # API 返回嵌套结构：data 是销售维度数组，每个销售下有 records 数组
    # 需要展平为记录列表，合并销售信息到每条记录
    if isinstance(data, list):
        flattened_records = []
        for sales_item in data:
            sales_user_id = sales_item.get("salesUserId")
            sales_name = sales_item.get("salesName")
            records = sales_item.get("records", [])
            for record in records:
                # 将销售信息合并到每条记录中
                record["salesUserId"] = sales_user_id
                record["salesName"] = sales_name
                flattened_records.append(record)
        return flattened_records
    elif isinstance(data, dict):
        # 处理可能的 dict 格式响应
        raw_list = data.get("list", data.get("items", []))
        flattened_records = []
        for sales_item in raw_list:
            sales_user_id = sales_item.get("salesUserId")
            sales_name = sales_item.get("salesName")
            records = sales_item.get("records", [])
            for record in records:
                record["salesUserId"] = sales_user_id
                record["salesName"] = sales_name
                flattened_records.append(record)
        return flattened_records
    return []


def get_text_records(
    sales_user_id: str,
    customer_wechat_no: str = None,
    start_time: int = None,
    end_time: int = None,
) -> list:
    """获取文本类型的云客沟通记录（过滤 recordType == "text"）"""
    records = get_communication_records(
        sales_user_id=sales_user_id,
        customer_wechat_no=customer_wechat_no,
        start_time=start_time,
        end_time=end_time,
    )
    return [r for r in records if r.get("recordType") == "text"]


# ---------------------------------------------------------------------------
# 格式转换：云客沟通记录 → 质检 Agent 期望的内部格式
# ---------------------------------------------------------------------------

def transform_record(record: dict) -> dict:
    """将云客 API 的单条记录转为质检 Agent 期望的内部格式

    映射规则（与虎鲸 get_chat_records 返回格式对齐）：
    - content          → sentence
    - direction        → type (1=send, 2=receive) + author ("right"=send, "left"=receive)
    - msgTime (ms)     → time (秒级时间戳字符串)
    - recordType       → msg_type
    - sortTime (ms)    → key (排序用)
    """
    direction = record.get("direction", "")
    msg_type = 1 if direction == "send" else 2 if direction == "receive" else 0
    author = "right" if direction == "send" else "left"

    msg_time = record.get("msgTime", "0")
    try:
        # 云客 msgTime 为毫秒时间戳，转为秒
        time_sec = str(int(int(msg_time) / 1000))
        # 格式化为 YYYY-MM-DD HH:MM:SS（东八区）
        create_time = datetime.fromtimestamp(
            int(msg_time) / 1000, tz=_TZ_SHANGHAI
        ).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        time_sec = "0"
        create_time = ""

    sort_time = record.get("sortTime", 0)
    try:
        sort_key = int(sort_time)
    except (ValueError, TypeError):
        sort_key = 0

    return {
        "sentence": record.get("content", ""),
        "type": msg_type,
        "author": author,
        "time": time_sec,
        "createTime": create_time,
        "msg_type": record.get("recordType", ""),
        "key": sort_key,
        "channel": record.get("channel", ""),
    }


def transform_records(records: list) -> list:
    """批量转换记录列表，并按 sortTime 升序排序"""
    transformed = [transform_record(r) for r in records]
    # 按 key（sortTime 毫秒时间戳）升序
    transformed.sort(key=lambda r: r.get("key", 0))
    return transformed


def get_chat_records_for_quality_check(
    sales_user_id: str,
    customer_wechat_no: str,
    end_time_str: str,
    start_time_str: str = None,
    chat_days: int = None,
    max_records: int = None,
) -> list:
    """获取质检专用的聊天记录（时间范围 + 条数限制）

    与虎鲸的 get_chat_records_for_quality_check 功能对齐，但使用新接口。

    Args:
        sales_user_id: 销售用户 ID
        customer_wechat_no: 客户微信号
        end_time_str: 质检结束时间，格式 "YYYY-MM-DD HH:MM:SS"
        start_time_str: 质检开始时间，格式 "YYYY-MM-DD HH:MM:SS"；
                        如果提供则直接使用，不再往前推 chat_days 天
        chat_days: 往前查询天数（仅在 start_time_str 未提供时生效），
                   默认使用配置 QUALITY_CHECK_CHAT_DAYS
        max_records: 最大聊天记录条数，默认使用配置 QUALITY_CHECK_MAX_CHAT_RECORDS

    Returns:
        转换后的聊天记录列表（质检 Agent 格式）
    """
    if max_records is None:
        max_records = settings.QUALITY_CHECK_MAX_CHAT_RECORDS

    # 计算时间范围（Unix 秒级时间戳）
    end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_TZ_SHANGHAI)
    if start_time_str:
        # 直接使用前端传入的起始时间
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_TZ_SHANGHAI)
    else:
        # 兼容旧逻辑：往前推 chat_days 天
        if chat_days is None:
            chat_days = settings.QUALITY_CHECK_CHAT_DAYS
        start_dt = end_dt - timedelta(days=chat_days)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    logger.info(
        f"[comm质检] salesUserId={sales_user_id}, customerWechatNo={customer_wechat_no}, "
        f"时间范围: {start_dt} ~ {end_dt}"
    )

    # 获取文本类型的云客沟通记录
    records = get_text_records(
        sales_user_id=sales_user_id,
        customer_wechat_no=customer_wechat_no,
        start_time=start_ts,
        end_time=end_ts,
    )

    # 条数限制：保留最新的 max_records 条（已按 sortTime 升序排列）
    if len(records) > max_records:
        logger.info(f"[comm质检] 获取 {len(records)} 条，截取最新 {max_records} 条")
        records = records[-max_records:]
    else:
        logger.info(f"[comm质检] 获取 {len(records)} 条，无需截取")

    # 转换格式
    return transform_records(records)
