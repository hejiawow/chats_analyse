# -*- coding: utf-8 -*-
"""Regression tests for system user IDs vs Hujing sales user IDs.

The app cannot be imported in the lightweight test environment unless the
production PostgreSQL driver is installed, so this guards the exact regression:
trigger endpoints must not copy the system account ID into the Hujing sales ID
request field.
"""
from pathlib import Path
import unittest


class TriggerUserIdBoundaryTest(unittest.TestCase):
    def test_trigger_endpoints_do_not_overwrite_hujing_user_id_with_system_user_id(self):
        main_py = Path(__file__).resolve().parents[1] / "app" / "main.py"
        source = main_py.read_text(encoding="utf-8")
        forbidden = 'req.user_id = str(current_user["user_id"])'

        self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
