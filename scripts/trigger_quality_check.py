# -*- coding: utf-8 -*-
"""
命令行触发批量质检分析

通过 Celery 提交 run_batch_quality_check_by_messages 任务，
CLI 快速退出，适合 crontab 定时调度。

使用方式：
    # 默认：过去 24 小时全量扫描
    python scripts/trigger_quality_check.py

    # 指定时间范围
    python scripts/trigger_quality_check.py --start-time "2026-06-01 00:00:00" --end-time "2026-06-01 23:59:59"

    # 筛选特定销售
    python scripts/trigger_quality_check.py --user-id "sales_001"

    # 模拟运行（不实际提交）
    python scripts/trigger_quality_check.py --dry-run

    # 强制提交（跳过锁检查）
    python scripts/trigger_quality_check.py --force

Crontab 配置示例：
    # 每小时整点执行
    0 * * * * cd /opt/chats_analyse && docker compose exec -T worker python scripts/trigger_quality_check.py >> /var/log/quality_check_cron.log 2>&1
"""
import os
import sys
import uuid
import argparse
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis

from config import settings


# Redis 锁配置
LOCK_KEY = "batch:quality:cli_lock"
LOCK_TTL = 10800  # 3 小时
PROGRESS_KEY_PREFIX = "batch:progress:"


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg):
    print(f"[{_now_str()}] {msg}", flush=True)


def acquire_lock(redis_client, task_id):
    """获取 Redis 分布式锁，返回 True/False"""
    return redis_client.set(LOCK_KEY, task_id, nx=True, ex=LOCK_TTL)


def find_running_task(redis_client):
    """扫描 Redis 中正在运行的批量质检任务，返回 (task_id, progress_dict) 或 None"""
    for key in redis_client.scan_iter(f"{PROGRESS_KEY_PREFIX}*"):
        data = redis_client.get(key)
        if not data:
            continue
        try:
            import json
            progress = json.loads(data)
            if progress.get("status") == "running":
                task_id = key.split(PROGRESS_KEY_PREFIX, 1)[1]
                return task_id, progress
        except (ValueError, TypeError):
            continue
    return None


def build_parser():
    parser = argparse.ArgumentParser(
        description="命令行触发批量质检分析（quality_check）",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        help="检测开始时间，格式 'YYYY-MM-DD HH:MM:SS'，默认过去 24 小时",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default=None,
        help="检测结束时间，格式 'YYYY-MM-DD HH:MM:SS'，默认当前时间",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="筛选特定销售 ID（可选，默认全量）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="最大分析数量（默认 500）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="跳过锁检查，强制提交",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印参数，不实际提交任务",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # 计算时间范围
    now = datetime.now()
    end_time = args.end_time or now.strftime("%Y-%m-%d %H:%M:%S")
    start_time = args.start_time or (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    user_label = args.user_id or "全部"

    # dry-run 模式
    if args.dry_run:
        _log("[DRY-RUN] 模拟提交批量质检任务")
        print(f"  时间范围:   {start_time} ~ {end_time}")
        print(f"  销售筛选:   {user_label}")
        print(f"  最大数量:   {args.limit}")
        return 0

    # 初始化 Redis
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.ping()
    except Exception as e:
        _log(f"[错误] Redis 连接失败: {e}")
        return 1

    # 检查锁
    if not args.force:
        lock_holder = redis_client.get(LOCK_KEY)
        if lock_holder:
            _log("上一次质检任务仍在运行，跳过本次提交")
            print(f"  运行中 task_id: {lock_holder}")
            print(f"  提示: 使用 --force 可强制提交")
            return 0

        # 额外检查：是否有 running 状态的任务
        running = find_running_task(redis_client)
        if running:
            running_id, progress = running
            _log("检测到正在运行的批量质检任务，跳过本次提交")
            print(f"  运行中 task_id: {running_id}")
            print(f"  进度: {progress.get('completed', 0)}/{progress.get('total', 0)}")
            print(f"  提示: 使用 --force 可强制提交")
            return 0

    # 生成 task_id
    task_id = str(uuid.uuid4())

    # 提交 Celery 任务
    try:
        from app.tasks.batch_quality import run_batch_quality_check_by_messages

        run_batch_quality_check_by_messages.delay(
            batch_task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            user_id_filter=args.user_id,
            limit=args.limit,
        )
    except Exception as e:
        _log(f"[错误] 提交任务失败: {e}")
        return 1

    # 获取锁（提交成功后才加锁）
    if not args.force:
        acquire_lock(redis_client, task_id)

    _log("批量质检任务已提交")
    print(f"  task_id:    {task_id}")
    print(f"  时间范围:   {start_time} ~ {end_time}")
    print(f"  销售筛选:   {user_label}")
    print(f"  最大数量:   {args.limit}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
