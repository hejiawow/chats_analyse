# -*- coding: utf-8 -*-
"""质检批量聊天对过滤规则测试"""
import unittest
from unittest.mock import patch

from app.services.refund_filter import filter_matched_pairs


class _ImmediateFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class RefundFilterTest(unittest.TestCase):
    def test_filters_friend_name_containing_ahu_in_memory_mode(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "left",
                "sentence": "我要退费",
                "create_time": "2026-06-05 10:00:00",
            }
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 101,
                 "user_id": "sales-1",
                 "nick": "客户阿虎小号",
             }) as mock_get_friend:
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [])
        mock_get_friend.assert_called_once_with(101)

    def test_fetches_precise_friend_info_with_ten_workers(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": str(friend_id),
                "author": "left",
                "sentence": "我要退费",
                "create_time": "2026-06-05 10:00:00",
            }
            for friend_id in range(100, 112)
        ]
        matched_pairs = [("sales-1", friend_id) for friend_id in range(100, 112)]

        submitted_futures = []

        def submit_friend(_fn, friend_id):
            future = _ImmediateFuture({"id": friend_id, "nick": "真实客户"})
            submitted_futures.append(future)
            return future

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 100,
                 "nick": "真实客户",
             }), \
             patch("app.services.refund_filter.ThreadPoolExecutor") as mock_executor, \
             patch("app.services.refund_filter.as_completed", side_effect=lambda futures: submitted_futures):
            mock_executor.return_value.__enter__.return_value.submit.side_effect = submit_friend
            result = filter_matched_pairs(
                matched_pairs,
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, matched_pairs)
        mock_executor.assert_called_once_with(max_workers=10)

    def test_does_not_filter_ahu_in_remark_when_nick_is_regular(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "left",
                "sentence": "我要退费",
                "create_time": "2026-06-05 10:00:00",
            }
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 101,
                 "user_id": "sales-1",
                 "nick": "真实客户",
                 "remark": "阿虎测试小号",
             }):
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [("sales-1", 101)])

    def test_keeps_pair_when_precise_friend_api_returns_none(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "left",
                "sentence": "我要退费",
                "create_time": "2026-06-05 10:00:00",
            }
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value=None):
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [("sales-1", 101)])

    def test_does_not_filter_ahu_in_non_friend_name_fields(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "left",
                "sentence": "我要退费",
                "create_time": "2026-06-05 10:00:00",
            }
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 101,
                 "user_id": "sales-1",
                 "nick": "微信昵称",
                 "remark": "",
                 "friendName": "阿虎不应参与过滤",
                 "chat_title": "阿虎不应参与过滤",
             }):
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [("sales-1", 101)])

    def test_filters_pair_without_customer_messages_in_memory_mode(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "right",
                "sentence": "客户说要退费，我转发一下话术",
                "create_time": "2026-06-05 10:00:00",
            }
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 101,
                 "user_id": "sales-1",
                 "nick": "真实客户",
             }):
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [])

    def test_keeps_pair_with_customer_message_and_regular_friend_name(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "right",
                "sentence": "您好",
                "create_time": "2026-06-05 09:59:00",
            },
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "left",
                "sentence": "我要退费",
                "create_time": "2026-06-05 10:00:00",
            },
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=[]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 101,
                 "user_id": "sales-1",
                 "nick": "真实客户",
             }):
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [("sales-1", 101)])

    def test_still_filters_protocol_triggered_refund(self):
        all_messages = [
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "right",
                "sentence": "这是协议话术",
                "create_time": "2026-06-05 10:00:00",
            },
            {
                "user_id": "sales-1",
                "friend_id": "101",
                "author": "left",
                "sentence": "那我要退费",
                "create_time": "2026-06-05 10:01:00",
            },
        ]

        with patch("app.services.refund_filter.get_whitelist_patterns", return_value=["协议话术"]), \
             patch("app.services.refund_filter.get_chat_friend_info", return_value={
                 "id": 101,
                 "user_id": "sales-1",
                 "nick": "真实客户",
             }):
            result = filter_matched_pairs(
                [("sales-1", 101)],
                "2026-06-05 00:00:00",
                "2026-06-05 23:59:59",
                all_messages=all_messages,
            )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
