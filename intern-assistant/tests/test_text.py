# -*- coding: utf-8 -*-
"""文本工具测试：清洗、业务字数口径、相对日期解析（多轮上下文支撑）。"""

import datetime
import os
import sys

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.utils.text import cjk_len, clean_text, parse_relative_date, truncate


class TestCleanText:
    def test_collapses_whitespace(self):
        assert clean_text("  请假\n\t  三天  ") == "请假 三天"

    def test_empty_safe(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""


class TestCjkLen:
    def test_pure_chinese_counts_chars(self):
        assert cjk_len("今天巡检了设备") == 7

    def test_ascii_words_count_as_words(self):
        # 连续 ASCII 串算 1 词："点检SOP2026版" → 中文 3（点检/版）+ 词 1 = 4
        assert cjk_len("点检SOP2026版") == 4

    def test_mixed_text(self):
        # 中文 4（今天巡检）+ 单词 "OA" = 5
        assert cjk_len("今天巡检OA") == 5

    def test_empty_safe(self):
        assert cjk_len("") == 0


class TestTruncate:
    def test_short_text_untouched(self):
        assert truncate("短文本", 200) == "短文本"

    def test_long_text_appends_ellipsis(self):
        out = truncate("字" * 300, 200)
        assert out.startswith("字" * 200) and out.endswith("…")


class TestParseRelativeDate:
    base = datetime.date(2026, 11, 5)   # 周四

    def test_today(self):
        assert parse_relative_date("今天", self.base) == self.base

    def test_tomorrow(self):
        assert parse_relative_date("明天", self.base) == datetime.date(2026, 11, 6)

    def test_day_after_tomorrow(self):
        assert parse_relative_date("后天", self.base) == datetime.date(2026, 11, 7)

    def test_next_week_monday(self):
        # 周四(11-05)的"下周一" → 下一个自然周的周一 = 11-09
        assert parse_relative_date("下周一", self.base) == datetime.date(2026, 11, 9)

    def test_next_week_sunday(self):
        assert parse_relative_date("下周日", self.base) == datetime.date(2026, 11, 15)

    def test_this_week_friday(self):
        assert parse_relative_date("本周五", self.base) == datetime.date(2026, 11, 6)

    def test_embedded_in_sentence(self):
        # 多轮上下文场景："从下周一开始请假"
        assert parse_relative_date("我想从下周一开始请假", self.base) == datetime.date(2026, 11, 9)

    def test_unparseable_returns_none(self):
        assert parse_relative_date("11月20日", self.base) is None
        assert parse_relative_date("", self.base) is None
