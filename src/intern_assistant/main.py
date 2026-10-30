# -*- coding: utf-8 -*-
"""程序入口：python -m intern_assistant.main"""

import os
import sys

# 保证 src 目录在 sys.path 中（未 pip install 时也能直接运行）
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import uvicorn  # noqa: E402


def main() -> None:
    uvicorn.run("intern_assistant.core.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
