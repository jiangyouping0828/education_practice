# -*- coding: utf-8 -*-
"""通用小工具函数：历史入口保持 re-export，具体实现在同包各模块中。

- digest / mask_phone / mask_idcard → utils.security
- clean_text / cjk_len / truncate / parse_relative_date → utils.text
"""
from .security import digest, mask_all, mask_idcard, mask_phone  # noqa: F401
from .text import clean_text, cjk_len, parse_relative_date, truncate  # noqa: F401

__all__ = [
    "digest", "mask_phone", "mask_idcard", "mask_all",
    "clean_text", "cjk_len", "truncate", "parse_relative_date",
]
