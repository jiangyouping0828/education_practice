# -*- coding: utf-8 -*-
"""通用小工具函数。"""


def digest(text: str, limit: int = 200) -> str:
    """截断文本作为日志摘要（日志最小化，避免落明文敏感内容）。"""
    text = (text or "").strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


def mask_phone(text: str) -> str:
    """手机号脱敏：138****1234。"""
    import re
    return re.sub(r"(1[3-9]\d)\d{4}(\d{4})", r"\1****\2", text or "")


def mask_idcard(text: str) -> str:
    """身份证号脱敏：保留前 4 后 2。"""
    import re
    return re.sub(r"(\d{4})\d{12}(\d{2}[\dXx])", r"\1**************\2", text or "")
