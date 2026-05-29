# -*- coding: utf-8 -*-
"""提示词加载器 — 从 prompts/ 目录读取 .md 提示词模板"""
import pathlib

# 固定为本文件所在目录，不依赖 CWD
_PROMPTS_DIR = pathlib.Path(__file__).parent.resolve()

_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """加载提示词模板。

    Args:
        name: 文件名（可带或不带 .md 后缀），如 "referral_check"

    Returns:
        提示词原文，保留所有 {placeholder} 占位符供 LangChain 使用

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not name.endswith(".md"):
        name = name + ".md"

    if name in _cache:
        return _cache[name]

    file_path = _PROMPTS_DIR / name
    if not file_path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    text = file_path.read_text(encoding="utf-8")
    _cache[name] = text
    return text
