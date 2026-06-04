# -*- coding: utf-8 -*-
"""质检处理建议卡结构化结果测试"""
import json
import unittest


class QualityGuidanceAgentTest(unittest.TestCase):
    def test_parse_failed_response_returns_manual_review_guidance(self):
        from app.agents.quality_check import _parse_ai_response

        result = _parse_ai_response("not-json")

        self.assertEqual(result["risk_level"], "unknown")
        self.assertEqual(result["action_priority"], "P1")
        self.assertEqual(result["recommended_owner"], "质检")
        self.assertEqual(result["action_type"], "主管复核")
        self.assertTrue(result["needs_manual_review"])
        self.assertIn("guidance", result)

    def test_normalize_quality_result_clamps_and_sanitizes_fields(self):
        from app.agents.quality_check import _normalize_quality_result

        raw = {
            "risk_level": "bad",
            "risk_category": "",
            "trigger_party": "nobody",
            "issue_summary": "x" * 80,
            "action_priority": "urgent",
            "recommended_owner": "机器人",
            "action_type": "未知动作",
            "follow_up_deadline": "下周",
            "needs_manual_review": "yes",
            "confidence": 3,
            "guidance": {"risk_reason": "客户要求退款"},
            "key_evidence": [{"content": "我要退款"}],
        }

        result = _normalize_quality_result(raw)

        self.assertEqual(result["risk_level"], "unknown")
        self.assertEqual(result["risk_category"], "其他")
        self.assertIsNone(result["trigger_party"])
        self.assertEqual(len(result["issue_summary"]), 50)
        self.assertEqual(result["action_priority"], "P1")
        self.assertEqual(result["recommended_owner"], "质检")
        self.assertEqual(result["action_type"], "主管复核")
        self.assertEqual(result["follow_up_deadline"], "今日内")
        self.assertTrue(result["needs_manual_review"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["guidance"]["risk_reason"], "客户要求退款")
        self.assertEqual(result["key_evidence"][0]["content"], "我要退款")

    def test_normalize_no_keyword_result_is_p3_no_action(self):
        from app.agents.quality_check import _normalize_quality_result

        result = _normalize_quality_result({
            "risk_level": "none",
            "risk_category": "无风险",
            "trigger_party": "none",
            "issue_summary": "未检测到风险关键词",
        })

        self.assertEqual(result["action_priority"], "P3")
        self.assertEqual(result["recommended_owner"], "无需处理")
        self.assertEqual(result["action_type"], "无需处理")
        self.assertEqual(result["follow_up_deadline"], "无需跟进")
        self.assertFalse(result["needs_manual_review"])


class QualityGuidanceModelTest(unittest.TestCase):
    def test_result_to_dict_contains_list_fields_but_not_detail_json(self):
        from app.models.result import QualityCheckResult

        record = QualityCheckResult(
            user_id="sales-1",
            friend_id=101,
            risk_level="high",
            risk_category="退款",
            issue_summary="客户明确要求退款",
            action_priority="P1",
            recommended_owner="客服",
            action_type="客服跟进",
            follow_up_deadline="今日内",
            needs_manual_review=True,
            confidence=0.86,
            process_status="pending",
        )

        data = record.to_dict()

        self.assertEqual(data["issue_summary"], "客户明确要求退款")
        self.assertEqual(data["action_priority"], "P1")
        self.assertEqual(data["recommended_owner"], "客服")
        self.assertEqual(data["action_type"], "客服跟进")
        self.assertEqual(data["follow_up_deadline"], "今日内")
        self.assertTrue(data["needs_manual_review"])
        self.assertEqual(data["confidence"], 0.86)
        self.assertEqual(data["process_status"], "pending")
        self.assertNotIn("guidance", data)
        self.assertNotIn("keyword_matches", data)
        self.assertNotIn("key_evidence", data)
        self.assertNotIn("raw_response", data)

    def test_detail_to_dict_returns_guidance(self):
        from app.models.result import QualityCheckDetail

        detail = QualityCheckDetail(
            result_id=1,
            guidance={"risk_reason": "客户明确要求退款"},
            key_evidence=[{"content": "我要退款", "reason": "明确诉求"}],
        )

        data = detail.to_dict()

        self.assertEqual(data["guidance"]["risk_reason"], "客户明确要求退款")
        self.assertEqual(data["key_evidence"][0]["reason"], "明确诉求")

    def test_prompt_requires_new_structured_fields(self):
        from pathlib import Path

        prompt = (Path(__file__).resolve().parents[1] / "app" / "prompts" / "quality_check.md").read_text(encoding="utf-8")
        required_terms = [
            "issue_summary",
            "action_priority",
            "recommended_owner",
            "follow_up_deadline",
            "needs_manual_review",
            "guidance",
            "reply_suggestion",
        ]

        missing = [term for term in required_terms if term not in prompt]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
