# -*- coding: utf-8 -*-
"""管理员密码重置脚本（忘记密码时的救援通道）。

用法：
    PYTHONPATH=src python scripts/reset_admin.py            # 交互提示输入
    PYTHONPATH=src python scripts/reset_admin.py 新密码      # 直接指定

安全说明：仅重置 role='admin' 的账号；新密码走与登录一致的
sha256("ims_" + pwd) 哈希，脚本不落明文日志。
"""

import getpass
import os
import sys

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import sqlite3  # noqa: E402

from intern_assistant.core.app import DB_PATH, hash_pwd  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        pwd = sys.argv[1]
    else:
        pwd = getpass.getpass("请输入新密码（输入不回显）：")
        pwd2 = getpass.getpass("请再次输入确认：")
        if pwd != pwd2:
            print("[FAIL] 两次输入不一致，未做任何修改")
            return 1
    if len(pwd) < 8:
        print("[FAIL] 密码至少 8 位（含字母与数字更佳）")
        return 1
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "UPDATE users SET password_hash=? WHERE role='admin'", (hash_pwd(pwd),))
    conn.commit()
    conn.close()
    print(f"[OK] 已重置 {cur.rowcount} 个管理员账号的密码，请重新登录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
