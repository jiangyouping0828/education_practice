# -*- coding: utf-8 -*-
"""数据库备份脚本：带时间戳备份 + 按份数保留。

用法：
    PYTHONPATH=src python scripts/backup.py            # 备份，保留最近 10 份
    PYTHONPATH=src python scripts/backup.py --keep 30  # 自定义保留份数

说明：与 `python -m intern_assistant.cli backup` 等价，独立成脚本便于
配合系统计划任务（Windows 任务计划 / cron）做每日自动备份。
"""

import os
import shutil
import sys
import time

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.core.app import DB_PATH  # noqa: E402


def main() -> int:
    keep = 10
    if "--keep" in sys.argv:
        keep = int(sys.argv[sys.argv.index("--keep") + 1])
    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(backup_dir, f"chat_{stamp}.db")
    shutil.copy2(DB_PATH, dst)
    backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("chat_"))
    removed = 0
    for old in backups[:max(0, len(backups) - keep)]:
        os.remove(os.path.join(backup_dir, old))
        removed += 1
    print(f"[OK] 备份完成：{dst}")
    if removed:
        print(f"[OK] 清理 {removed} 份过期备份（保留最近 {keep} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
