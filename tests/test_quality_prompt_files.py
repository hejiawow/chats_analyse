# -*- coding: utf-8 -*-
"""优化版质检提示词文件测试"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_prompt(name: str) -> str:
    return (ROOT / "app" / "prompts" / name).read_text(encoding="utf-8")


def test_optimized_quality_check_prompt_contains_initial_guardrails():
    text = read_prompt("quality_check_optimized.md")

    required_markers = [
        "最高优先级：售前/售中排除规则",
        "trigger_party = sales 时",
        "不能是退款/投诉/监管介入/取消订单",
        "客户在售前阶段说\"不买了\"",
        "P0：客户明确提出外部监管级投诉",
        "{keyword_matches}",
        "{context_messages}",
    ]
    for marker in required_markers:
        assert marker in text


def test_optimized_quality_review_prompt_contains_review_guardrails():
    text = read_prompt("quality_review_optimized.md")

    required_markers = [
        "销售推销行为不等于客户退费意图",
        "微信系统安全提示",
        "初次分析常见偏差类型",
        "first_mention_time_corrected",
        "initial_deviation_type",
        "{initial_risk_level}",
        "{raw_response}",
        "{chat_records}",
    ]
    for marker in required_markers:
        assert marker in text
