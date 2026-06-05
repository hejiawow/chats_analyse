# -*- coding: utf-8 -*-
"""质检结果前端静态回归测试"""
from pathlib import Path
import unittest


class QualityResultsFrontendTest(unittest.TestCase):
    def test_table_sorting_falls_back_to_column_key_for_custom_render_columns(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "src"
            / "views"
            / "QualityResults.vue"
        ).read_text(encoding="utf-8")

        self.assertIn("sorter?.field || sorter?.columnKey", source)

    def test_list_stats_and_export_all_send_processing_filters(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "src"
            / "views"
            / "QualityResults.vue"
        ).read_text(encoding="utf-8")

        for param in (
            "keywords",
            "action_priorities",
            "risk_categories",
            "recommended_owner",
            "action_type",
            "needs_manual_review",
            "process_status",
        ):
            self.assertGreaterEqual(source.count(f"params.{param} = filters.{param}"), 3)


if __name__ == "__main__":
    unittest.main()
