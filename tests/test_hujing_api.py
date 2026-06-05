# -*- coding: utf-8 -*-
"""虎鲸 API 服务回归测试"""
import unittest
from unittest.mock import Mock, patch


class HujingApiTest(unittest.TestCase):
    @patch("app.services.hujing_api.get_friends_list")
    @patch("app.services.hujing_api.cache_get", return_value=None)
    def test_get_friends_batch_without_progress_callback_does_not_call_none(self, _mock_cache_get, mock_get_friends_list):
        from app.services.hujing_api import get_friends_batch

        mock_get_friends_list.return_value = [{"friendId": 101, "nick": "真实客户"}]

        result = get_friends_batch(["sales-1"])

        self.assertEqual(result, {"sales-1": [{"friendId": 101, "nick": "真实客户"}]})

    @patch("app.services.hujing_api.settings")
    @patch("app.services.hujing_api.requests.get")
    def test_get_chat_friend_info_uses_chat_api_base_and_key(self, mock_get, mock_settings):
        from app.services.hujing_api import get_chat_friend_info

        mock_settings.HUJING_CHAT_API_URL = "https://chat-api.example.com"
        mock_settings.HUJING_CHAT_API_KEY = "secret-key"
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"id": 101, "nick": "客户阿虎小号"}
        mock_get.return_value = response

        result = get_chat_friend_info(101)

        self.assertEqual(result, {"id": 101, "nick": "客户阿虎小号"})
        mock_get.assert_called_once_with(
            "https://chat-api.example.com/api/v1/chat/friends/101",
            headers={"x-api-key": "secret-key"},
            timeout=30,
            verify=False,
        )

    @patch("app.services.hujing_api.settings")
    @patch("app.services.hujing_api.requests.get")
    def test_get_chat_friend_info_returns_none_when_not_found(self, mock_get, mock_settings):
        from app.services.hujing_api import get_chat_friend_info

        mock_settings.HUJING_CHAT_API_URL = "https://chat-api.example.com"
        mock_settings.HUJING_CHAT_API_KEY = "secret-key"
        response = Mock()
        response.status_code = 404
        mock_get.return_value = response

        result = get_chat_friend_info(404)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
