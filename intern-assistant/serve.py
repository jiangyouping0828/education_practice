# -*- coding: utf-8 -*-
"""云端部署入口：python serve.py

与 python -m intern_assistant.main 的区别：
- 自动把 src 加入 sys.path，不依赖 PYTHONPATH 环境变量；
- 默认 HOST=0.0.0.0（云沙箱要求对外监听），PORT 优先取平台注入的环境变量。
本地开发仍推荐 scripts/run.bat（默认 127.0.0.1:8000）。
"""
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.main import main  # noqa: E402

if __name__ == "__main__":
    os.environ.setdefault("HOST", "0.0.0.0")
    main()
