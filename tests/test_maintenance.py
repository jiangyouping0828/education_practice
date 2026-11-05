# -*- coding: utf-8 -*-
"""maintenance.py 测试：dry-run 与真实删除、保留期边界、票据清理。"""

import os
import sqlite3
import sys
import time

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.core import maintenance

SCHEMA = """
CREATE TABLE admin_tokens (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE student_tokens (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE agent_rounds (id INTEGER PRIMARY KEY, session_id TEXT, tool_name TEXT,
                           status TEXT, duration_ms INTEGER, created_at REAL, args_json TEXT,
                           result_digest TEXT, round_no INTEGER);
CREATE TABLE tool_audit_log (id INTEGER PRIMARY KEY, created_at REAL);
CREATE TABLE admin_access_log (id INTEGER PRIMARY KEY, created_at REAL);
CREATE TABLE apply_tickets (ticket TEXT PRIMARY KEY, user_id TEXT, apply_type TEXT,
                            payload TEXT, payload_hash TEXT, issued_at REAL,
                            expires_at REAL, used_at REAL);
"""


def fresh_db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.executescript(SCHEMA)
    now = time.time()
    # 令牌：1 过期 1 有效
    conn.execute("INSERT INTO admin_tokens VALUES ('a1','u',?)", (now - 10,))
    conn.execute("INSERT INTO admin_tokens VALUES ('a2','u',?)", (now + 3600,))
    conn.execute("INSERT INTO student_tokens VALUES ('s1','u',?)", (now - 10,))
    # 日志：2 条 200 天前、2 条刚刚
    old, new = now - 200 * 86400, now
    for t in (old, old, new, new):
        conn.execute("INSERT INTO agent_rounds (session_id,tool_name,status,duration_ms,created_at)"
                     " VALUES ('x','search_policy','ok',5,?)", (t,))
        conn.execute("INSERT INTO tool_audit_log (created_at) VALUES (?)", (t,))
        conn.execute("INSERT INTO admin_access_log (created_at) VALUES (?)", (t,))
    # 票据：过期未用 / 过期已用 / 有效未用（used_at 用 NULL 表示未核销）
    conn.execute("INSERT INTO apply_tickets VALUES ('t1','u','leave','{}','h',?,?,NULL)",
                 (now - 60, now - 30))
    conn.execute("INSERT INTO apply_tickets VALUES ('t2','u','leave','{}','h',?,?,'')",
                 (now - 60, now - 30))
    conn.execute("UPDATE apply_tickets SET used_at=? WHERE ticket='t2'", (now - 20,))
    conn.execute("INSERT INTO apply_tickets VALUES ('t3','u','leave','{}','h',?,?,NULL)",
                 (now, now + 600))
    conn.commit()
    return conn


class TestTokens:
    def test_dry_run_counts_but_keeps(self, tmp_path):
        conn = fresh_db(tmp_path)
        n = maintenance.purge_expired_tokens(conn, dry_run=True)
        assert n == 2
        assert conn.execute("SELECT COUNT(*) FROM admin_tokens").fetchone()[0] == 2

    def test_exec_deletes_only_expired(self, tmp_path):
        conn = fresh_db(tmp_path)
        maintenance.purge_expired_tokens(conn, dry_run=False)
        assert conn.execute("SELECT COUNT(*) FROM admin_tokens").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM student_tokens").fetchone()[0] == 0


class TestLogs:
    def test_dry_run_reports(self, tmp_path):
        conn = fresh_db(tmp_path)
        stats = maintenance.purge_old_logs(conn, days=180, dry_run=True)
        assert stats == {"agent_rounds": 2, "tool_audit_log": 2, "admin_access_log": 2}

    def test_exec_deletes_old_only(self, tmp_path):
        conn = fresh_db(tmp_path)
        maintenance.purge_old_logs(conn, days=180, dry_run=False)
        assert conn.execute("SELECT COUNT(*) FROM agent_rounds").fetchone()[0] == 2

    def test_missing_table_reported_minus_one(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "empty.db"))
        conn.execute("CREATE TABLE agent_rounds (created_at REAL)")
        stats = maintenance.purge_old_logs(conn, dry_run=True)
        assert stats["tool_audit_log"] == -1 and stats["admin_access_log"] == -1


class TestTickets:
    def test_only_unused_expired_removed(self, tmp_path):
        conn = fresh_db(tmp_path)
        n = maintenance.purge_expired_tickets(conn, dry_run=False)
        assert n == 1        # t1 过期未用；t2 过期但已核销（留证）；t3 有效
        remain = {r[0] for r in conn.execute("SELECT ticket FROM apply_tickets")}
        assert remain == {"t2", "t3"}

    def test_dry_run_no_change(self, tmp_path):
        conn = fresh_db(tmp_path)
        assert maintenance.purge_expired_tickets(conn, dry_run=True) == 1
        assert conn.execute("SELECT COUNT(*) FROM apply_tickets").fetchone()[0] == 3


class TestRunMaintenance:
    def test_summary_shape(self, tmp_path):
        stats = maintenance.run_maintenance(str(tmp_path / "t.db"), dry_run=True)
        assert set(stats) == {"dry_run", "expired_tokens", "old_logs", "expired_tickets"}
        assert stats["dry_run"] is True
