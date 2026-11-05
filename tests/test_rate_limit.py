# -*- coding: utf-8 -*-
"""限流器测试：分钟/天双窗口判定与重置。"""

import os
import sys
import time
from unittest.mock import patch

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.core.rate_limit import SlidingWindowRateLimiter


class TestMinuteWindow:
    def test_allows_up_to_limit_then_rejects(self):
        rl = SlidingWindowRateLimiter(per_minute=3, per_day=100)
        for _ in range(3):
            assert rl.check("u1")[0] is True
        ok, reason = rl.check("u1")
        assert ok is False and "一分钟" in reason

    def test_keys_are_independent(self):
        rl = SlidingWindowRateLimiter(per_minute=1, per_day=100)
        assert rl.check("a")[0] is True
        assert rl.check("b")[0] is True
        assert rl.check("a")[0] is False


class TestDayWindow:
    def test_daily_cap(self):
        rl = SlidingWindowRateLimiter(per_minute=1000, per_day=5)
        for _ in range(5):
            assert rl.check("u1")[0] is True
        ok, reason = rl.check("u1")
        assert ok is False and "上限" in reason

    def test_old_hits_expire(self):
        rl = SlidingWindowRateLimiter(per_minute=2, per_day=100)
        with patch("intern_assistant.core.rate_limit.time.time",
                   side_effect=lambda: 1000.0):
            assert rl.check("u1")[0] is True
            assert rl.check("u1")[0] is True
            assert rl.check("u1")[0] is False
        # 时间前进 61 秒后分钟窗口过期
        with patch("intern_assistant.core.rate_limit.time.time",
                   side_effect=lambda: 1000.0 + 61):
            assert rl.check("u1")[0] is True


class TestReset:
    def test_reset_single_key(self):
        rl = SlidingWindowRateLimiter(per_minute=1, per_day=100)
        assert rl.check("u1")[0] is True
        assert rl.check("u1")[0] is False
        rl.reset("u1")
        assert rl.check("u1")[0] is True

    def test_reset_all(self):
        rl = SlidingWindowRateLimiter(per_minute=1, per_day=100)
        rl.check("a"); rl.check("b")
        rl.reset()
        assert rl.check("a")[0] is True
