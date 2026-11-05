# -*- coding: utf-8 -*-
"""限流器（core.rate_limit）：进程内滑动窗口限流，保护 LLM 配额。

上线检查清单要求：单用户 10 次/分钟、100 次/天，超限返 429 不产生计费调用。
进程内实现适合单实例部署；多实例部署时换 Redis 后端，接口保持不变。
"""

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple


class SlidingWindowRateLimiter:
    """按 (key, 窗口) 双窗口限流：minute 窗口 + day 窗口同时判定。"""

    def __init__(self, per_minute: int = 10, per_day: int = 100) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, dq: Deque[float], now: float, window: float) -> None:
        while dq and dq[0] <= now - window:
            dq.popleft()

    def check(self, key: str) -> Tuple[bool, str]:
        """判定是否放行。返回 (allowed, 拒绝原因)；拒绝原因用于构造 429 提示。"""
        now = time.time()
        with self._lock:
            dq = self._hits[key]
            # 分钟窗口
            self._prune(dq, now, 60)
            if len(dq) >= self.per_minute:
                return False, "提问太频繁，请稍等一分钟再试"
            # 天窗口（按自然日 86400 秒近似，重启后清零——限流是保护而非记账）
            day_hits = sum(1 for t in dq if t > now - 86400)
            if day_hits >= self.per_day:
                return False, "今日提问次数已达上限，请明天再来"
            dq.append(now)
            return True, ""

    def reset(self, key: str = "") -> None:
        """清空计数（测试与运维用；不带参数清空全部）。"""
        with self._lock:
            if key:
                self._hits.pop(key, None)
            else:
                self._hits.clear()
