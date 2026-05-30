# -*- coding: utf-8 -*-
"""虎鲸 API 服务封装"""
import hashlib
import logging
import time
import requests
from datetime import datetime, timedelta
from requests.exceptions import ConnectTimeout, ConnectionError, RequestException

from config import settings
from app.services.cache import cache_get, cache_set, cache_clear_pattern

# 缓存过期时间（秒）
_SALES_CACHE_TTL = 21600       # 销售列表：6 小时
_FRIENDS_CACHE_TTL = 21600     # 好友列表：6 小时
_DEPARTMENT_CACHE_TTL = 3600   # 组织架构：1 小时

logger = logging.getLogger(__name__)


def generate_sign() -> tuple[str, int]:
    timestamp = int(time.time())
    sign_str = f"{settings.HUJING_APP_ID}{timestamp}{settings.HUJING_APP_KEY}"
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    return sign, timestamp


def _build_headers() -> dict:
    sign, timestamp = generate_sign()
    return {
        "appid": settings.HUJING_APP_ID,
        "timestamp": str(timestamp),
        "sign": sign,
    }


def _request(url: str, form_data: dict, max_retries: int = 3, timeout: int = 30) -> dict | None:
    """带重试的 POST 请求"""
    import time as _time

    headers = _build_headers()
    for retry in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=form_data, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                return result.get("data", {})
        except (ConnectTimeout, ConnectionError, RequestException):
            if retry < max_retries - 1:
                _time.sleep(2 ** retry)
    return None


def get_chat_records(user_id: str, friend_id: int, start_time: str = "2000-01-01 00:00:00",
                     end_time: str = "2099-12-31 23:59:59", page_size: int = 1000000) -> list:
    """获取聊天记录（自动分页）"""
    all_chats = []
    base_url = f"{settings.HUJING_API_BASE_URL}/api/chat/showChatByUser"

    for current_page in range(1, 51):
        data = _request(base_url, {
            "app_id": settings.HUJING_APP_ID,
            "user_id": user_id,
            "friend_id": friend_id,
            "start_time": start_time,
            "end_time": end_time,
            "page": current_page,
            "page_size": page_size,
        }, max_retries=1, timeout=30)

        if data is None:
            break

        chat_list = data.get("result", [])
        if not chat_list:
            break

        all_chats.extend(chat_list)
        if len(chat_list) < page_size:
            break

    return sorted(all_chats, key=lambda x: x.get("key", 0))


def get_all_sales(page: int = 1, page_size: int = 1000000) -> list:
    """获取销售列表（带缓存）"""
    cache_key = f"hujing:sales:{page}:{page_size}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.HUJING_API_BASE_URL}/api/user/getAllUser"
    data = _request(url, {
        "app_id": settings.HUJING_APP_ID,
        "page": page,
        "page_size": page_size,
    })
    if data:
        result = data.get("result", [])
        cache_set(cache_key, result, _SALES_CACHE_TTL)
        return result
    return []


def resolve_user_id_by_name(username: str) -> str | None:
    """通过销售姓名查找 user_id（返回第一个匹配）"""
    sales_list = get_all_sales()
    for sale in sales_list:
        if sale.get("username") == username:
            return sale.get("user_id")
    return None


def find_sales_by_name_with_friend(username: str, identifier: str) -> list:
    """
    通过销售姓名 + 好友标识（手机号/微信号/备注手机号）查找匹配的销售-好友对。
    返回 [{"user_id": str, "username": str, "friend_id": int, "friend_info": dict}, ...]
    """
    sales_list = get_all_sales()
    matched = []

    for sale in sales_list:
        if sale.get("username") != username:
            continue

        user_id = sale.get("user_id")
        if not user_id:
            continue

        # 检查该销售的好友列表中是否有匹配的标识
        friends = get_friends_list(user_id)
        for f in friends:
            if _match_friend(f, identifier):
                matched.append({
                    "user_id": user_id,
                    "username": username,
                    "friend_id": f.get("friendId"),
                    "friend_nick": f.get("nick") or f.get("remark") or "",
                    "friend_wx_id": f.get("friend_wx_id") or "",
                })
                break  # 每个销售只取一个匹配的好友

    return matched


def resolve_friend_id_by_phone(user_id: str, phone: str) -> tuple[int | None, dict | None]:
    """通过手机号/备注手机号查找好友ID，返回 (friend_id, friend_info)"""
    friends_list = get_friends_list(user_id)
    for f in friends_list:
        if f.get("phone") == phone or f.get("remark_phone") == phone:
            return f.get("friendId"), f
    return None, None


def resolve_friend_by_identifier(user_id: str, identifier: str) -> tuple[int | None, dict | None]:
    """通过好友标识（手机号/微信号/备注手机号）查找好友ID，返回 (friend_id, friend_info)"""
    friends_list = get_friends_list(user_id)
    for f in friends_list:
        if _match_friend(f, identifier):
            return f.get("friendId"), f
    return None, None


def _match_friend(friend: dict, identifier: str) -> bool:
    """判断好友信息是否匹配给定的标识（手机号或微信号）"""
    # 手机号匹配
    if friend.get("phone") == identifier:
        return True
    # 备注手机号匹配
    if friend.get("remark_phone") == identifier:
        return True
    # 联系方式手机号匹配
    # if friend.get("contacts_phone") == identifier:
    #     return True
    # 微信号匹配（friend_wx_id 是实际微信号，alias 可能是自定义微信号）
    if friend.get("friend_wx_id") == identifier:
        return True
    # 客户别名匹配
    if friend.get("alias") == identifier:
        return True
    return False


def get_friends_list(user_id: str, is_group: str = "0", skip_deleted: bool = True) -> list:
    """获取好友列表（单页 + 去重 + 过滤已删除）（带缓存）"""
    cache_key = f"hujing:friends:{user_id}:{is_group}"
    cached = cache_get(cache_key)
    if cached is not None:
        if skip_deleted:
            return [f for f in cached if f.get("is_deleted") != 1]
        return cached

    url = f"{settings.HUJING_API_BASE_URL}/api/friend/getAllFriendByUserId"
    data = _request(url, {
        "app_id": settings.HUJING_APP_ID,
        "user_id": user_id,
        "is_group": is_group,
        "page": 1,
        "page_size": 1000000,
    })

    if data is None:
        return []

    friends_list = data.get("result", [])
    seen_ids = set()
    unique_friends = []
    for f in friends_list:
        fid = f.get("friendId")
        if fid not in seen_ids:
            seen_ids.add(fid)
            unique_friends.append(f)

    def _safe_parse_time(t: str) -> datetime:
        """安全解析时间字符串，异常时返回最小值"""
        try:
            return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return datetime.min

    sorted_friends = sorted(unique_friends, key=lambda x: _safe_parse_time(x.get("createTime", "")))
    # 缓存原始数据（不缓存 skip_deleted 过滤结果）
    cache_set(cache_key, sorted_friends, _FRIENDS_CACHE_TTL)
    if skip_deleted:
        return [f for f in sorted_friends if f.get("is_deleted") != 1]
    return sorted_friends


def get_friends_batch(user_ids: list[str]) -> dict[str, list[dict]]:
    """批量获取多个销售的好友列表（带缓存）

    Args:
        user_ids: 销售 ID 列表

    Returns:
        {user_id: [friend_info, ...]} 映射字典
    """
    result = {}
    for user_id in user_ids:
        # 利用现有的缓存机制
        friends = get_friends_list(user_id)
        result[user_id] = friends
    return result


def invalidate_sales_cache() -> None:
    """清空销售相关缓存（在新增/删除销售后调用）"""
    cache_clear_pattern("hujing:sales:*")


def invalidate_friend_cache(user_id: str = None) -> None:
    """清空指定销售的好友缓存，不传 user_id 则清空所有"""
    if user_id:
        cache_clear_pattern(f"hujing:friends:{user_id}:*")
    else:
        cache_clear_pattern("hujing:friends:*")


def get_department_tree() -> dict:
    """获取部门人员组织架构树（带缓存）

    Returns:
        {
            "departments": [...],  # 部门列表（扁平化）
            "sales": [...],        # 所有销售人员列表
        }
    """
    cache_key = "hujing:department_tree"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.HUJING_API_BASE_URL}/api/dept/list"
    data = _request(url, {
        "app_id": settings.HUJING_APP_ID,
    })

    if data is None:
        return {"departments": [], "sales": []}

    # 解析树形结构，提取部门列表和销售列表
    departments = []
    sales = []

    def parse_tree(node_list):
        """递归解析部门树"""
        if not node_list:
            return

        for node in node_list:
            # 提取部门信息
            dept = {
                "id": node.get("id"),
                "name": node.get("name"),
                "parent_id": node.get("parent_id"),
                "level": node.get("level"),
            }
            departments.append(dept)

            # 提取该部门下的销售人员
            users = node.get("users") or []
            for user in users:
                sale = {
                    "sales_id": user.get("sales_id"),
                    "username": user.get("username"),
                    "department_id": user.get("department_id"),
                    "department_name": user.get("department_name") or node.get("name"),
                }
                sales.append(sale)

            # 递归处理子部门
            children = node.get("children") or []
            parse_tree(children)

    parse_tree(data if isinstance(data, list) else [data])

    result = {
        "departments": departments,
        "sales": sales,
    }

    cache_set(cache_key, result, _DEPARTMENT_CACHE_TTL)
    return result


def find_sales_by_department_and_name(department_name: str, username: str) -> list:
    """通过部门名称和销售姓名查找销售

    Args:
        department_name: 部门名称（精确匹配）
        username: 销售姓名（精确匹配）

    Returns:
        [
            {
                "sales_id": "xxx",
                "username": "xxx",
                "department_id": xxx,
                "department_name": "xxx"
            }
        ]
    """
    org = get_department_tree()
    matched = []

    for sale in org.get("sales", []):
        if sale.get("username") == username:
            # 如果指定了部门，需要部门匹配
            if department_name:
                if sale.get("department_name") == department_name:
                    matched.append(sale)
            else:
                # 未指定部门，直接匹配姓名
                matched.append(sale)

    return matched


def invalidate_department_cache() -> None:
    """清空组织架构缓存"""
    cache_clear_pattern("hujing:department_tree")


def get_chat_pairs(start_time: str, end_time: str, page_size: int = 10000) -> dict:
    """获取指定时间范围内有聊天记录的所有 user_id + friend_id 组合

    Args:
        start_time: 开始时间，格式 "YYYY-MM-DD HH:MM:SS"
        end_time: 结束时间，格式 "YYYY-MM-DD HH:MM:SS"
        page_size: 每页数量，默认 10000

    Returns:
        {
            "total": 444,
            "data": [{"user_id": "xxx", "friend_id": 123}, ...]
        }
    """
    url = f"{settings.HUJING_CHAT_API_URL}/api/v1/chat/pairs"
    headers = {
        "x-api-key": settings.HUJING_CHAT_API_KEY,
    }
    params = {
        "start_time": start_time,
        "end_time": end_time,
        "page": 1,
        "page_size": page_size,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        return {
            "total": result.get("total", 0),
            "data": result.get("data", []),
        }
    except RequestException as e:
        logger.error(f"get_chat_pairs error: {e}")
        return {"total": 0, "data": [], "error": str(e)}


def get_all_chat_messages(start_time: str, end_time: str, page_size: int = 10000) -> list:
    """获取指定时间范围内所有聊天记录（新接口）

    注意：新接口限制时间范围不能超过2天，因此需要分段请求。

    Args:
        start_time: 开始时间，格式 "YYYY-MM-DD HH:MM:SS"
        end_time: 结束时间，格式 "YYYY-MM-DD HH:MM:SS"
        page_size: 每页数量，默认 10000

    Returns:
        聊天记录列表，每条记录包含 user_id, friend_id, sentence 等字段
    """
    url = f"{settings.HUJING_CHAT_API_URL}/api/v1/chat/messages"
    headers = {
        "x-api-key": settings.HUJING_CHAT_API_KEY,
    }
    
    all_messages = []
    
    # 将字符串时间转换为 datetime 对象
    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    
    # 计算总时间跨度
    total_duration = end_dt - start_dt
    
    # 使用1.9天（约45.6小时）作为分段间隔，确保不会超过2天限制
    # 避免边界条件问题
    max_duration = timedelta(days=1.9)
    
    # 强制分段，不依赖时间差判断
    segments = []
    current_start = start_dt

    while current_start < end_dt:
        current_end = min(current_start + max_duration, end_dt)
        seg_start_str = current_start.strftime("%Y-%m-%d %H:%M:%S")
        seg_end_str = current_end.strftime("%Y-%m-%d %H:%M:%S")
        segments.append((seg_start_str, seg_end_str))
        current_start = current_end
    
    # 遍历每个时间段进行请求
    for seg_start, seg_end in segments:
        page = 1
        while True:
            params = {
                "start_time": seg_start,
                "end_time": seg_end,
                "page": page,
                "page_size": page_size,
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=60)
                response.raise_for_status()
                result = response.json()
                
                data = result.get("data", [])
                if not data:
                    break
                
                all_messages.extend(data)
                
                total = result.get("total", 0)
                if len(all_messages) >= total:
                    break
                
                page += 1
                
            except RequestException as e:
                try:
                    response_text = response.text if 'response' in locals() else 'N/A'
                    logger.error(f"get_all_chat_messages error: {e}")
                    logger.debug(f"Response content: {response_text[:500]}")
                except:
                    logger.error(f"get_all_chat_messages error: {e}")
                break

    return all_messages
