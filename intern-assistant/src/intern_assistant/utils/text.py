# -*- coding: utf-8 -*-
"""文本工具（utils.text）：清洗、中文字数、相对日期解析、摘要。"""

import datetime
import re
from typing import Optional

from .security import digest  # re-export，保持向后兼容的导入路径

__all__ = ["clean_text", "cjk_len", "truncate", "digest", "parse_relative_date"]

# ---- 清洗与计数 -------------------------------------------------------------


def clean_text(text: str) -> str:
    """用户输入清洗：压缩连续空白为单个空格、去首尾空白。

    不删除任何业务字符（学生可能输入多行周报内容），只做展示级净化。
    """
    return re.sub(r"\s+", " ", text or "").strip()


def cjk_len(text: str) -> int:
    """业务字数统计：中文字符按 1 计，连续 ASCII 词（英文/数字）按 1 词计。

    与制度"周报≥30字"等阈值保持同一口径，避免中英混排时阈值失真。
    """
    if not text:
        return 0
    ascii_words = len(re.findall(r"[A-Za-z0-9]+", text))
    cjk_chars = len(re.sub(r"[A-Za-z0-9\s\W]", "", text, flags=re.UNICODE))
    return ascii_words + cjk_chars


def truncate(text: str, limit: int = 200) -> str:
    """按字符数截断并追加省略号（日志摘要用）。"""
    text = (text or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


# ---- 相对日期解析（多轮上下文场景："从下周一开始请假"）----------------------

_WEEKDAY_ZH = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def parse_relative_date(text: str, today: Optional[datetime.date] = None) -> Optional[datetime.date]:
    """把口语日期解析为具体日期；无法解析返回 None。

    支持："今天" "明天" "后天" "下周X" "周X"（本周内）。
    用途：多轮上下文中学生说"从下周一开始请假"，智能体追问日期前可先尝试解析。
    """
    t = (text or "").strip()
    if not t:
        return None
    base = today or datetime.date.today()

    if t == "今天":
        return base
    if t == "明天":
        return base + datetime.timedelta(days=1)
    if t == "后天":
        return base + datetime.timedelta(days=2)
    m = re.search(r"(?:下周|下个周|下礼拜)([一二三四五六日天])", t)
    if m:  # 下周：严格取下一个自然周的对应星期
        target = _WEEKDAY_ZH[m.group(1)]
        days_ahead = 7 - base.weekday() + target
        return base + datetime.timedelta(days=days_ahead)
    m = re.search(r"(?:本?周|本?礼拜)([一二三四五六日天])", t)
    if m:  # 本周：取本周对应星期（可能已过去，返回过去日期由业务层判断）
        target = _WEEKDAY_ZH[m.group(1)]
        return base + datetime.timedelta(days=target - base.weekday())
    return None
