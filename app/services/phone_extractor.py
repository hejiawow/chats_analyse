# -*- coding: utf-8 -*-
"""手机号提取工具 — 从备注手机号和好友备注中提取报班手机号"""
import re

_PHONE_RE = re.compile(r'1[3-9]\d{9}')
_PHONE_STRICT_RE = re.compile(r'^1[3-9]\d{9}$')


def extract_enrollment_phones(remark_phone: str | None, chat_title: str | None) -> dict:
    """从备注手机号和好友备注中提取报班手机号

    逻辑：
    1. remark_phone 严格校验（完整 11 位），有效则作为报班手机号
    2. 从 chat_title 正则提取手机号：
       - 若报班手机号为空，则填入报班手机号
       - 若与报班手机号不同，则填入第二报班手机号

    Returns:
        {"enrollment_phone": str|None, "enrollment_phone_2": str|None}
    """
    enrollment_phone = None
    enrollment_phone_2 = None

    # 1. 从 remark_phone 提取（严格校验：完整 11 位）
    if remark_phone and _PHONE_STRICT_RE.match(remark_phone.strip()):
        enrollment_phone = remark_phone.strip()

    # 2. 从 chat_title 正则提取
    if chat_title:
        match = _PHONE_RE.search(chat_title)
        if match:
            chat_phone = match.group()
            if not enrollment_phone:
                enrollment_phone = chat_phone
            elif chat_phone != enrollment_phone:
                enrollment_phone_2 = chat_phone

    return {"enrollment_phone": enrollment_phone, "enrollment_phone_2": enrollment_phone_2}
