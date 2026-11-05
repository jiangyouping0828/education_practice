# -*- coding: utf-8 -*-
"""pytest 全局前置：在任何测试模块导入应用之前，把数据库指到临时文件。

这样 test_core.py / test_isolation.py 合跑时不会误用 data/runtime/chat.db，
也不会被正在运行的开发服务锁影响。
"""

import os
import sys
import tempfile

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

_TMP_DB = os.path.join(tempfile.gettempdir(), "ims_test.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["IMS_DB_PATH"] = _TMP_DB
