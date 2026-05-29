# -*- coding: utf-8 -*-
"""
测试虎鲸 Chat Pairs API
直接运行此文件，输出 API 返回的 JSON 结果

使用方法:
    python test_chat_pairs_api.py
    python test_chat_pairs_api.py --start "2026-05-27 00:00:00" --end "2026-05-28 23:59:59"
    python test_chat_pairs_api.py --days 1
"""
import argparse
import json
import requests
from datetime import datetime, timedelta

# API 配置
HUJING_CHAT_API_URL = "http://192.168.20.217:8006"
HUJING_CHAT_API_KEY = "sgiwogSDF450AXVCSFF"


def get_chat_pairs(start_time: str, end_time: str, page_size: int = 100000) -> dict:
    """调用 Chat Pairs API"""
    url = f"{HUJING_CHAT_API_URL}/api/v1/chat/pairs"
    headers = {"x-api-key": HUJING_CHAT_API_KEY}
    params = {
        "start_time": start_time,
        "end_time": end_time,
        "page": 1,
        "page_size": page_size,
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="测试虎鲸 Chat Pairs API")
    parser.add_argument("--start", type=str, help="开始时间 YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end", type=str, help="结束时间 YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--days", type=int, default=2, help="时间范围天数（默认2天）")
    parser.add_argument("--page-size", type=int, default=5, help="每页数量（默认100000）")
    args = parser.parse_args()

    # 计算时间范围
    if args.start and args.end:
        start_time = args.start
        end_time = args.end
    else:
        now = datetime.now()
        start_dt = now - timedelta(days=args.days)
        start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    print(f"请求时间范围: {start_time} ~ {end_time}")
    print(f"每页数量: {args.page_size}")
    print("-" * 50)

    try:
        result = get_chat_pairs(start_time, end_time, args.page_size)

        # 输出完整 JSON
        print(json.dumps(result, indent=2, ensure_ascii=False))

        print("-" * 50)
        print(f"总计: {result.get('total')} 个聊天对")
        print(f"返回: {len(result.get('data', []))} 条数据")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP 错误: {e}")
        if e.response is not None:
            print(f"响应内容: {e.response.text}")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()