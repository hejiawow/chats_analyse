# -*- coding: utf-8 -*-
"""测试虎鲸 Chat Pairs API"""
from datetime import datetime, timedelta

# 直接调用虎鲸 API
import requests

HUJING_CHAT_API_URL = "http://192.168.20.217:8006"
HUJING_CHAT_API_KEY = "sgiwogSDF450AXVCSFF"


def test_chat_pairs():
    """测试获取聊天对 API"""
    # 时间范围：昨天此时到今天此时
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    start_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 60)
    print("测试虎鲸 Chat Pairs API")
    print("=" * 60)
    print(f"时间范围: {start_time} ~ {end_time}")
    print()

    url = f"{HUJING_CHAT_API_URL}/api/v1/chat/pairs"
    headers = {"x-api-key": HUJING_CHAT_API_KEY}
    params = {
        "start_time": start_time,
        "end_time": end_time,
        "page": 1,
        "page_size": 100,  # 只取100条测试
    }

    print(f"请求 URL: {url}")
    print(f"请求参数: {params}")
    print()

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        print("响应状态码:", response.status_code)
        print()
        print("=" * 60)
        print("返回结果结构:")
        print("=" * 60)
        print(f"total: {result.get('total')}")
        print(f"page: {result.get('page')}")
        print(f"page_size: {result.get('page_size')}")
        print(f"data 条数: {len(result.get('data', []))}")
        print()

        # 显示前10条数据
        print("=" * 60)
        print("前 10 条聊天对:")
        print("=" * 60)
        for i, pair in enumerate(result.get("data", [])[:10]):
            print(f"{i+1}. user_id: {pair.get('user_id')}, friend_id: {pair.get('friend_id')}")

        print()
        print("=" * 60)
        print("完整 JSON 响应（前100条）:")
        print("=" * 60)
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])  # 只显示前2000字符

    except Exception as e:
        print(f"请求失败: {e}")


if __name__ == "__main__":
    test_chat_pairs()