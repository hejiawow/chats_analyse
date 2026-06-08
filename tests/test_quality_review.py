# -*- coding: utf-8 -*-
"""质检二次审查智能体测试"""
import json
import unittest
from unittest.mock import Mock, patch, MagicMock


class CoerceConfidenceTest(unittest.TestCase):
    """测试置信度规范化函数"""

    def test_valid_number_within_range(self):
        from app.agents.quality_review import _coerce_confidence

        self.assertEqual(_coerce_confidence(0.5), 0.5)
        self.assertEqual(_coerce_confidence(0.0), 0.0)
        self.assertEqual(_coerce_confidence(1.0), 1.0)

    def test_number_exceeds_upper_bound(self):
        from app.agents.quality_review import _coerce_confidence

        self.assertEqual(_coerce_confidence(1.5), 1.0)
        self.assertEqual(_coerce_confidence(100), 1.0)

    def test_number_below_lower_bound(self):
        from app.agents.quality_review import _coerce_confidence

        self.assertEqual(_coerce_confidence(-0.5), 0.0)
        self.assertEqual(_coerce_confidence(-10), 0.0)

    def test_string_number(self):
        from app.agents.quality_review import _coerce_confidence

        self.assertEqual(_coerce_confidence("0.7"), 0.7)
        self.assertEqual(_coerce_confidence("invalid"), 0.0)

    def test_none_value(self):
        from app.agents.quality_review import _coerce_confidence

        self.assertEqual(_coerce_confidence(None), 0.0)

    def test_invalid_type(self):
        from app.agents.quality_review import _coerce_confidence

        self.assertEqual(_coerce_confidence([1, 2, 3]), 0.0)
        self.assertEqual(_coerce_confidence({"a": 1}), 0.0)


class NormalizeReviewResultTest(unittest.TestCase):
    """测试结果规范化函数"""

    def test_valid_input(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {
            "secondary_risk_level": "medium",
            "review_reason": "经复核，风险等级合理",
            "suggested_action": "主管复核",
            "confidence": 0.85
        }

        result = _normalize_review_result(raw)

        self.assertEqual(result["secondary_risk_level"], "medium")
        self.assertEqual(result["review_reason"], "经复核，风险等级合理")
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 0.85)

    def test_invalid_risk_level_defaults_to_unknown(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {
            "secondary_risk_level": "invalid",
            "review_reason": "测试",
            "suggested_action": "主管复核",
            "confidence": 0.5
        }

        result = _normalize_review_result(raw)

        self.assertEqual(result["secondary_risk_level"], "unknown")

    def test_empty_review_reason_gets_default(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {
            "secondary_risk_level": "low",
            "review_reason": "",
            "suggested_action": "误报观察",
            "confidence": 0.5
        }

        result = _normalize_review_result(raw)

        self.assertEqual(result["review_reason"], "AI响应缺少判断理由，请人工复核")

    def test_invalid_suggested_action_defaults_to_supervisor_review(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {
            "secondary_risk_level": "high",
            "review_reason": "测试",
            "suggested_action": "无效动作",
            "confidence": 0.5
        }

        result = _normalize_review_result(raw)

        self.assertEqual(result["suggested_action"], "主管复核")

    def test_long_review_reason_truncated(self):
        from app.agents.quality_review import _normalize_review_result

        long_reason = "x" * 600
        raw = {
            "secondary_risk_level": "medium",
            "review_reason": long_reason,
            "suggested_action": "主管复核",
            "confidence": 0.5
        }

        result = _normalize_review_result(raw)

        self.assertEqual(len(result["review_reason"]), 500)

    def test_none_input(self):
        from app.agents.quality_review import _normalize_review_result

        result = _normalize_review_result(None)

        self.assertEqual(result["secondary_risk_level"], "unknown")
        self.assertEqual(result["review_reason"], "AI响应缺少判断理由，请人工复核")
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 0.0)

    def test_missing_fields_get_defaults(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {}

        result = _normalize_review_result(raw)

        self.assertEqual(result["secondary_risk_level"], "unknown")
        self.assertEqual(result["review_reason"], "AI响应缺少判断理由，请人工复核")
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 0.0)

    def test_new_fields_with_valid_input(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {
            "confirmed": True,
            "risk_type": "退费",
            "priority": "P1",
            "first_mention_time": "2024-01-01 10:05:00",
            "secondary_risk_level": "high",
            "review_reason": "确认涉及退费",
            "suggested_action": "立即介入",
            "confidence": 0.9
        }

        result = _normalize_review_result(raw)

        self.assertEqual(result["confirmed"], True)
        self.assertEqual(result["risk_type"], "退费")
        self.assertEqual(result["priority"], "P1")
        self.assertEqual(result["first_mention_time"], "2024-01-01 10:05:00")

    def test_risk_type_defaults_to_other(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"risk_type": "invalid_type"}
        result = _normalize_review_result(raw)
        self.assertEqual(result["risk_type"], "其他")

    def test_priority_defaults_to_p2(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"priority": "invalid"}
        result = _normalize_review_result(raw)
        self.assertEqual(result["priority"], "P2")

    def test_confirmed_string_true(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"confirmed": "true"}
        result = _normalize_review_result(raw)
        self.assertEqual(result["confirmed"], True)

    def test_confirmed_string_false(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"confirmed": "false"}
        result = _normalize_review_result(raw)
        self.assertEqual(result["confirmed"], False)

    def test_confirmed_none(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"confirmed": None}
        result = _normalize_review_result(raw)
        self.assertIsNone(result["confirmed"])

    def test_first_mention_time_empty_string(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"first_mention_time": ""}
        result = _normalize_review_result(raw)
        self.assertIsNone(result["first_mention_time"])

    def test_risk_type_complaint(self):
        from app.agents.quality_review import _normalize_review_result

        raw = {"risk_type": "投诉"}
        result = _normalize_review_result(raw)
        self.assertEqual(result["risk_type"], "投诉")


class ParseAIResponseTest(unittest.TestCase):
    """测试AI响应解析函数"""

    def test_valid_json_response(self):
        from app.agents.quality_review import _parse_ai_response

        raw = '{"secondary_risk_level": "high", "review_reason": "高风险确认", "suggested_action": "立即介入", "confidence": 0.9}'
        result = _parse_ai_response(raw)

        self.assertEqual(result["secondary_risk_level"], "high")
        self.assertEqual(result["review_reason"], "高风险确认")
        self.assertEqual(result["suggested_action"], "立即介入")
        self.assertEqual(result["confidence"], 0.9)

    def test_json_with_surrounding_text(self):
        from app.agents.quality_review import _parse_ai_response

        raw = '这是分析结果：{"secondary_risk_level": "low", "review_reason": "低风险", "suggested_action": "误报观察", "confidence": 0.6}，以上是结果。'
        result = _parse_ai_response(raw)

        self.assertEqual(result["secondary_risk_level"], "low")
        self.assertEqual(result["review_reason"], "低风险")

    def test_invalid_json_returns_defaults(self):
        from app.agents.quality_review import _parse_ai_response

        raw = "这不是JSON格式"
        result = _parse_ai_response(raw)

        self.assertEqual(result["secondary_risk_level"], "unknown")
        self.assertEqual(result["review_reason"], "AI响应解析失败，请人工复核")
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 0.0)

    def test_partial_json_with_invalid_fields(self):
        from app.agents.quality_review import _parse_ai_response

        raw = '{"secondary_risk_level": "invalid", "review_reason": "", "suggested_action": "invalid", "confidence": 999}'
        result = _parse_ai_response(raw)

        self.assertEqual(result["secondary_risk_level"], "unknown")
        self.assertEqual(result["review_reason"], "AI响应缺少判断理由，请人工复核")
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 1.0)  # 999 clamped to 1.0


class FormatChatRecordsTest(unittest.TestCase):
    """测试聊天记录格式化函数"""

    def test_format_with_full_records(self):
        from app.agents.quality_review import _format_chat_records

        chat_records = [
            {"author": "right", "createTime": "2024-01-01 10:00:00", "sentence": "您好，请问有什么可以帮助您？"},
            {"author": "left", "createTime": "2024-01-01 10:00:05", "sentence": "我想咨询退款事宜"},
        ]

        result = _format_chat_records(chat_records)

        self.assertIn("【销售】2024-01-01 10:00:00: 您好，请问有什么可以帮助您？", result)
        self.assertIn("【客户】2024-01-01 10:00:05: 我想咨询退款事宜", result)

    def test_format_with_missing_fields(self):
        from app.agents.quality_review import _format_chat_records

        chat_records = [
            {"author": "right", "sentence": "测试消息"},
            {"createTime": "2024-01-01 10:00:00"},
        ]

        result = _format_chat_records(chat_records)

        self.assertIn("【销售】: 测试消息", result)
        self.assertIn("【客户】2024-01-01 10:00:00: ", result)

    def test_format_empty_list(self):
        from app.agents.quality_review import _format_chat_records

        result = _format_chat_records([])

        self.assertEqual(result, "")


class FormatKeyEvidenceTest(unittest.TestCase):
    """测试关键证据格式化函数"""

    def test_format_with_evidence(self):
        from app.agents.quality_review import _format_key_evidence

        key_evidence = [
            {"speaker": "客户", "time": "2024-01-01 10:00:05", "content": "我要退款"},
            {"speaker": "销售", "time": "2024-01-01 10:00:10", "content": "好的，我帮您处理"},
        ]

        result = _format_key_evidence(key_evidence)

        self.assertIn("【客户】2024-01-01 10:00:05: 我要退款", result)
        self.assertIn("【销售】2024-01-01 10:00:10: 好的，我帮您处理", result)

    def test_format_with_missing_fields(self):
        from app.agents.quality_review import _format_key_evidence

        key_evidence = [
            {"speaker": "客户", "content": "投诉"},
            {"time": "2024-01-01 10:00:00"},
        ]

        result = _format_key_evidence(key_evidence)

        self.assertIn("【客户】: 投诉", result)
        self.assertIn("【】2024-01-01 10:00:00: ", result)

    def test_format_empty_list(self):
        from app.agents.quality_review import _format_key_evidence

        result = _format_key_evidence([])

        self.assertEqual(result, "无关键证据")


class QualityReviewAgentIntegrationTest(unittest.TestCase):
    """测试Agent主函数"""

    @patch('app.agents.quality_review.get_ai_semaphore')
    @patch('app.agents.quality_review.ChatPromptTemplate')
    @patch('app.agents.quality_review.get_llm')
    @patch('app.agents.quality_review.load_prompt')
    def test_agent_success(self, mock_load_prompt, mock_get_llm, mock_chat_prompt, mock_get_semaphore):
        from app.agents.quality_review import quality_review_agent

        # Mock AI response chain
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value='{"confirmed": true, "risk_type": "退费", "priority": "P1", "first_mention_time": "2024-01-01 10:00:05", "secondary_risk_level": "medium", "review_reason": "复核后确认中等风险", "suggested_action": "主管复核", "confidence": 0.75}')

        mock_prompt = Mock()
        mock_prompt.__or__ = Mock(return_value=mock_chain)

        mock_llm = Mock()
        mock_llm.__or__ = Mock(return_value=mock_chain)

        mock_chain.__or__ = Mock(return_value=mock_chain)

        mock_chat_prompt.from_template = Mock(return_value=mock_prompt)
        mock_get_llm.return_value = mock_llm
        mock_load_prompt.return_value = "test prompt"

        # Mock semaphore
        mock_semaphore = MagicMock()
        mock_semaphore.__enter__ = Mock(return_value=None)
        mock_semaphore.__exit__ = Mock(return_value=None)
        mock_get_semaphore.return_value = mock_semaphore

        # Test data
        chat_records = [
            {"author": "right", "createTime": "2024-01-01 10:00:00", "sentence": "您好"},
            {"author": "left", "createTime": "2024-01-01 10:00:05", "sentence": "退款"},
        ]
        key_evidence = [
            {"speaker": "客户", "time": "2024-01-01 10:00:05", "content": "我要退款"}
        ]

        # Call agent
        result = quality_review_agent(
            result_id=1,
            chat_records=chat_records,
            key_evidence=key_evidence,
            issue_summary="客户要求退款",
            initial_risk_level="high"
        )

        # Verify
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["secondary_risk_level"], "medium")
        self.assertEqual(result["review_reason"], "复核后确认中等风险")
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 0.75)
        self.assertEqual(result["confirmed"], True)
        self.assertEqual(result["risk_type"], "退费")
        self.assertEqual(result["priority"], "P1")
        self.assertEqual(result["first_mention_time"], "2024-01-01 10:00:05")
        self.assertIn("raw_response", result)

    @patch('app.agents.quality_review.get_ai_semaphore')
    @patch('app.agents.quality_review.get_llm')
    @patch('app.agents.quality_review.load_prompt')
    def test_agent_ai_failure_returns_error(self, mock_load_prompt, mock_get_llm, mock_get_semaphore):
        from app.agents.quality_review import quality_review_agent

        # Mock AI failure
        mock_llm = Mock()
        mock_llm.invoke = Mock(side_effect=Exception("API Error"))
        mock_get_llm.return_value = mock_llm
        mock_load_prompt.return_value = "test prompt"

        # Mock semaphore
        mock_semaphore = MagicMock()
        mock_semaphore.__enter__ = Mock(return_value=None)
        mock_semaphore.__exit__ = Mock(return_value=None)
        mock_get_semaphore.return_value = mock_semaphore

        # Test data
        chat_records = [
            {"author": "right", "createTime": "2024-01-01 10:00:00", "sentence": "您好"},
        ]
        key_evidence = []

        # Call agent
        result = quality_review_agent(
            result_id=1,
            chat_records=chat_records,
            key_evidence=key_evidence,
            issue_summary="测试",
            initial_risk_level="low"
        )

        # Verify
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["secondary_risk_level"], "unknown")
        self.assertIn("AI分析失败", result["review_reason"])
        self.assertEqual(result["suggested_action"], "主管复核")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIsNone(result["raw_response"])
        self.assertIn("error_msg", result)


class AgentRegistrationTest(unittest.TestCase):
    """测试Agent注册"""

    def test_agent_registered_in_registry(self):
        from app.agents.registry import AgentRegistry

        # Import to trigger registration
        import app.agents.quality_review

        # Verify registration
        self.assertIn("质检二次审查", AgentRegistry._agents)
        # Verify it's callable
        agent_func = AgentRegistry.get("质检二次审查")
        self.assertIsNotNone(agent_func)
        self.assertTrue(callable(agent_func))


if __name__ == "__main__":
    unittest.main()