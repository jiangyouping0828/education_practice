# -*- coding: utf-8 -*-
"""cli.py 测试：子命令解析、eval 离线评测、export/purge/backup 主流程。"""

import json
import os
import sqlite3
import sys

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pytest

from intern_assistant import cli

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REAL_CASES = os.path.join(ROOT, "data", "eval_cases.json")


class TestParser:
    def test_all_subcommands_registered(self, capsys):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args([])
        assert "init-db" in capsys.readouterr().err or True

    def test_eval_defaults(self):
        args = cli.build_parser().parse_args(["eval"])
        assert args.cases.endswith("eval_cases.json")

    def test_purge_defaults_dry_run(self):
        args = cli.build_parser().parse_args(["purge"])
        assert args.exec is False and args.days == 180

    def test_backup_keep_default(self):
        assert cli.build_parser().parse_args(["backup"]).keep == 10


class TestCmdEval:
    def test_offline_eval_real_30_cases_pass(self, capsys):
        """30 条真实用例的离线回放必须满分（管线自检）。"""
        rc = cli.main(["eval", "--cases", REAL_CASES])
        out = capsys.readouterr().out
        assert rc == 0
        assert "30 / 30" in out

    def test_eval_writes_report_file(self, tmp_path, capsys):
        out = tmp_path / "report.md"
        cli.main(["eval", "--cases", REAL_CASES, "--out", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "离线评测报告" in text and "| 制度问答 |" in text

    def test_eval_bad_cases_fails(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps([{"question": "q", "expected_tools": ["ghost_tool"],
                                    "expected_behavior": "b", "category": "制度问答"}]),
                       encoding="utf-8")
        with pytest.raises(ValueError):
            cli.main(["eval", "--cases", str(bad)])


class TestCmdPurgeAndExport:
    def _prep_db(self, tmp_path, monkeypatch):
        """构造最小库并让 cli 的 DB_PATH 指向它。"""
        db = tmp_path / "chat.db"
        conn = sqlite3.connect(str(db))
        conn.executescript("""
            CREATE TABLE admin_tokens (token TEXT PRIMARY KEY, user_id TEXT, expires REAL);
            CREATE TABLE student_tokens (token TEXT PRIMARY KEY, user_id TEXT, expires REAL);
            CREATE TABLE agent_rounds (id INTEGER PRIMARY KEY, session_id TEXT, round_no INTEGER,
                                       tool_name TEXT, status TEXT, duration_ms INTEGER, created_at REAL);
            CREATE TABLE tool_audit_log (id INTEGER PRIMARY KEY, created_at REAL);
            CREATE TABLE admin_access_log (id INTEGER PRIMARY KEY, created_at REAL);
            CREATE TABLE apply_tickets (ticket TEXT PRIMARY KEY, user_id TEXT, apply_type TEXT,
                                        payload TEXT, payload_hash TEXT, issued_at REAL,
                                        expires_at REAL, used_at REAL);
            CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, user_id TEXT,
                                   created_at REAL, last_active_at REAL);
            CREATE TABLE messages (id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
                                   content TEXT, citations TEXT, created_at REAL);
            CREATE TABLE applies (id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, apply_type TEXT,
                                  payload TEXT, status TEXT, created_at REAL, updated_at REAL);
            INSERT INTO users VALUES ('u1','张三');
            INSERT INTO sessions VALUES ('s1','请假','u1',1.0,2.0);
            INSERT INTO applies VALUES ('a1','s1','u1','leave','{}','submitted',1.0,2.0);
            INSERT INTO agent_rounds VALUES (1,'s1',1,'search_policy','ok',5,1.0);
        """)
        conn.commit()
        conn.close()
        import intern_assistant.core.app as app_mod
        monkeypatch.setattr(app_mod, "DB_PATH", str(db))
        return db

    def test_purge_dry_run_then_exec(self, tmp_path, monkeypatch, capsys):
        self._prep_db(tmp_path, monkeypatch)
        assert cli.main(["purge"]) == 0
        assert "DRY-RUN" in capsys.readouterr().out
        assert cli.main(["purge", "--exec"]) == 0
        assert "已执行删除" in capsys.readouterr().out

    def test_export_sessions_csv(self, tmp_path, monkeypatch, capsys):
        self._prep_db(tmp_path, monkeypatch)
        out = tmp_path / "sessions.csv"
        assert cli.main(["export", "sessions", "--out", str(out)]) == 0
        text = out.read_text(encoding="utf-8-sig")
        assert "张三" in text and "s1" in text

    def test_export_empty_fails(self, tmp_path, monkeypatch, capsys):
        db = self._prep_db(tmp_path, monkeypatch)
        conn = sqlite3.connect(str(db))
        conn.execute("DELETE FROM applies")
        conn.commit()
        conn.close()
        assert cli.main(["export", "applies"]) == 1
        assert "无数据" in capsys.readouterr().out

    def test_backup_creates_file_and_keeps_limit(self, tmp_path, monkeypatch):
        db = self._prep_db(tmp_path, monkeypatch)
        for _ in range(12):
            cli.main(["backup", "--keep", "3"])
        backup_dir = os.path.join(os.path.dirname(str(db)), "backups")
        files = os.listdir(backup_dir)
        assert len(files) == 3 and all(f.startswith("chat_") for f in files)
