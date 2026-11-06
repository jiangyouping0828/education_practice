# -*- coding: utf-8 -*-
"""程序入口：python -m intern_assistant.main"""

import os
import sys

# 保证 src 目录在 sys.path 中（未 pip install 时也能直接运行）
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import uvicorn  # noqa: E402


def main() -> None:
    # 云端/沙箱部署：平台注入 PORT 环境变量时绑定 0.0.0.0:PORT；本地默认 127.0.0.1:8000 行为不变
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST") or ("0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    uvicorn.run("intern_assistant.core.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
