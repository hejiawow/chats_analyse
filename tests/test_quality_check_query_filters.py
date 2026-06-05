# -*- coding: utf-8 -*-
"""质检查询接口筛选回归测试"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class QualityCheckQueryFiltersTest(unittest.TestCase):
    def test_stats_endpoint_accepts_and_applies_processing_filters(self):
        source = (ROOT / "app" / "api" / "quality_check_query.py").read_text(encoding="utf-8")
        match = re.search(
            r"async def get_quality_check_stats\((.*?)\n\):(?P<body>.*?)\n\n@router\.get\(\"/quality-check/export\"\)",
            source,
            re.S,
        )
        self.assertIsNotNone(match)
        signature = match.group(1)
        body = match.group("body")

        for name in (
            "keywords",
            "action_priority",
            "recommended_owner",
            "action_type",
            "needs_manual_review",
            "process_status",
        ):
            self.assertIn(name, signature)

        self.assertIn("keyword_values", body)
        for stmt_name in ("count_stmt", "risk_stmt", "priority_stmt", "keyword_stmt"):
            self.assertRegex(body, rf"_apply_processing_filters\(\s*{stmt_name}")


if __name__ == "__main__":
    unittest.main()
