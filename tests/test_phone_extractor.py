# -*- coding: utf-8 -*-
"""phone_extractor 单元测试"""
import pytest
from app.services.phone_extractor import extract_enrollment_phones


class TestRemarkPhone:
    """remark_phone 校验逻辑"""

    def test_valid_11_digit(self):
        result = extract_enrollment_phones("13800138000", None)
        assert result == {"enrollment_phone": "13800138000", "enrollment_phone_2": None}

    def test_valid_with_whitespace(self):
        result = extract_enrollment_phones("  13800138000  ", None)
        assert result["enrollment_phone"] == "13800138000"

    def test_invalid_short(self):
        result = extract_enrollment_phones("1380013", None)
        assert result == {"enrollment_phone": None, "enrollment_phone_2": None}

    def test_invalid_starts_with_0(self):
        result = extract_enrollment_phones("03800138000", None)
        assert result["enrollment_phone"] is None

    def test_invalid_starts_with_2(self):
        result = extract_enrollment_phones("23800138000", None)
        assert result["enrollment_phone"] is None

    def test_invalid_too_long(self):
        result = extract_enrollment_phones("138001380001", None)
        assert result["enrollment_phone"] is None

    def test_invalid_non_digit(self):
        result = extract_enrollment_phones("1380013abcd", None)
        assert result["enrollment_phone"] is None

    def test_none(self):
        result = extract_enrollment_phones(None, None)
        assert result == {"enrollment_phone": None, "enrollment_phone_2": None}

    def test_empty_string(self):
        result = extract_enrollment_phones("", None)
        assert result == {"enrollment_phone": None, "enrollment_phone_2": None}


class TestChatTitle:
    """chat_title 正则提取逻辑"""

    def test_phone_in_title_no_remark(self):
        result = extract_enrollment_phones(None, "张三 13800138000")
        assert result["enrollment_phone"] == "13800138000"
        assert result["enrollment_phone_2"] is None

    def test_phone_in_title_with_remark_same(self):
        # chat_title 手机号与 remark_phone 相同，不填第二手机号
        result = extract_enrollment_phones("13800138000", "张三 13800138000")
        assert result["enrollment_phone"] == "13800138000"
        assert result["enrollment_phone_2"] is None

    def test_phone_in_title_with_remark_different(self):
        # chat_title 手机号与 remark_phone 不同，填入第二手机号
        result = extract_enrollment_phones("13800138000", "张三 13900139000")
        assert result["enrollment_phone"] == "13800138000"
        assert result["enrollment_phone_2"] == "13900139000"

    def test_no_phone_in_title(self):
        result = extract_enrollment_phones(None, "张三 备注信息")
        assert result == {"enrollment_phone": None, "enrollment_phone_2": None}

    def test_empty_title(self):
        result = extract_enrollment_phones("13800138000", "")
        assert result["enrollment_phone"] == "13800138000"
        assert result["enrollment_phone_2"] is None


class TestBothNone:
    """两者均为 None 或空字符串"""

    def test_both_none(self):
        assert extract_enrollment_phones(None, None) == {
            "enrollment_phone": None, "enrollment_phone_2": None
        }

    def test_both_empty(self):
        assert extract_enrollment_phones("", "") == {
            "enrollment_phone": None, "enrollment_phone_2": None
        }
