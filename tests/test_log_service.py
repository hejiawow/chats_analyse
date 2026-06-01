# -*- coding: utf-8 -*-
"""测试共享日志服务"""
import json
import unittest
from unittest.mock import patch, MagicMock


class TestLogService(unittest.TestCase):
    """测试 app.services.log_service 核心功能"""

    @patch("app.services.log_service.redis_client")
    def test_log_writes_to_redis_with_correct_key(self, mock_redis):
        from app.services.log_service import log, LOGS_KEY_PREFIX
        log("task-123", "测试消息", "info")
        mock_redis.rpush.assert_called_once()
        call_args = mock_redis.rpush.call_args
        assert call_args[0][0] == f"{LOGS_KEY_PREFIX}task-123"
        entry = json.loads(call_args[0][1])
        assert entry["level"] == "info"
        assert entry["message"] == "测试消息"
        assert "time" in entry

    @patch("app.services.log_service.redis_client")
    def test_log_sets_ttl(self, mock_redis):
        from app.services.log_service import log, LOGS_KEY_PREFIX
        log("task-123", "消息")
        mock_redis.expire.assert_called_once_with(f"{LOGS_KEY_PREFIX}task-123", 7200)

    @patch("app.services.log_service.redis_client")
    def test_log_does_not_raise_on_redis_failure(self, mock_redis):
        from app.services.log_service import log
        mock_redis.rpush.side_effect = Exception("Connection refused")
        log("task-123", "消息")  # 不应抛异常

    @patch("app.services.log_service.redis_client")
    def test_log_error_level(self, mock_redis):
        from app.services.log_service import log
        log("task-123", "出错了", "error")
        call_args = mock_redis.rpush.call_args
        entry = json.loads(call_args[0][1])
        assert entry["level"] == "error"

    @patch("app.services.log_service.redis_client")
    def test_get_task_logs_parses_entries(self, mock_redis):
        from app.services.log_service import get_task_logs
        mock_redis.lrange.return_value = [
            json.dumps({"time": "12:00:00", "level": "info", "message": "msg1"}),
            json.dumps({"time": "12:00:01", "level": "error", "message": "msg2"}),
        ]
        result = get_task_logs("task-123")
        assert len(result) == 2
        assert result[0]["message"] == "msg1"
        assert result[1]["level"] == "error"

    @patch("app.services.log_service.redis_client")
    def test_get_task_logs_skips_invalid_json(self, mock_redis):
        from app.services.log_service import get_task_logs
        mock_redis.lrange.return_value = [
            json.dumps({"time": "12:00:00", "level": "info", "message": "ok"}),
            "invalid json",
        ]
        result = get_task_logs("task-123")
        assert len(result) == 1

    @patch("app.services.log_service.redis_client")
    def test_mark_and_is_task_done(self, mock_redis):
        from app.services.log_service import mark_task_done, is_task_done, DONE_KEY_PREFIX
        mock_redis.get.return_value = "1"
        mark_task_done("task-123")
        mock_redis.set.assert_called_once_with(f"{DONE_KEY_PREFIX}task-123", "1", ex=3600)
        assert is_task_done("task-123") is True

    @patch("app.services.log_service.redis_client")
    def test_is_task_done_false(self, mock_redis):
        from app.services.log_service import is_task_done
        mock_redis.get.return_value = None
        assert is_task_done("task-123") is False

    @patch("app.services.log_service.redis_client")
    def test_clear_task_logs(self, mock_redis):
        from app.services.log_service import clear_task_logs, LOGS_KEY_PREFIX, DONE_KEY_PREFIX
        clear_task_logs("task-123")
        assert mock_redis.delete.call_count == 2
        mock_redis.delete.assert_any_call(f"{LOGS_KEY_PREFIX}task-123")
        mock_redis.delete.assert_any_call(f"{DONE_KEY_PREFIX}task-123")


if __name__ == "__main__":
    unittest.main()
