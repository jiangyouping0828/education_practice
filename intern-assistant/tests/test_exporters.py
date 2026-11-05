# -*- coding: utf-8 -*-
"""exporters.py 测试：CSV 渲染（BOM/列裁剪）、三种导出、Markdown 纪要。"""

import os
import sqlite3
import sys
import time

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pytest

from intern_assistant import exporters

SCHEMA = """
CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, user_id TEXT,
                       created_at REAL, last_active_at REAL);
CREATE TABLE messages (id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
                       content TEXT, citations TEXT, created_at REAL);
CREATE TABLE applies (id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, apply_type TEXT,
                      payload TEXT, status TEXT, created_at REAL, updated_at REAL);
CREATE TABLE agent_rounds (id INTEGER PRIMARY KEY, session_id TEXT, round_no INTEGER,
                           tool_name TEXT, status TEXT, duration_ms INTEGER, created_at REAL);
"""


@pytest.fixture()
def db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.executescript(SCHEMA)
    now = time.time()
    conn.execute("INSERT INTO users VALUES ('u1','张三')")
    conn.execute("INSERT INTO sessions VALUES ('s1','请假咨询','u1',?,?)", (now, now))
    conn.execute("INSERT INTO messages VALUES ('m1','s1','user','请问请假流程？','',?)", (now,))
    conn.execute("INSERT INTO messages VALUES ('m2','s1','assistant','按制度…','[{\"doc\":\"考勤\"}]',?)",
                 (now + 1,))
    conn.execute("INSERT INTO applies VALUES ('a1','s1','u1','leave','{}','submitted',?,?)",
                 (now, now))
    conn.execute("INSERT INTO agent_rounds VALUES (1,'s1',1,'search_policy','ok',5,?)", (now,))
    conn.commit()
    yield conn
    conn.close()


class TestToCsv:
    def test_bom_and_header(self):
        csv_text = exporters.to_csv([{"a": 1, "b": 2}])
        assert csv_text.startswith("\ufeff") and "a,b" in csv_text

    def test_column_subset(self):
        csv_text = exporters.to_csv([{"a": 1, "b": 2, "c": 3}], columns=["b", "a"])
        lines = csv_text.lstrip("\ufeff").strip().splitlines()
        assert lines[0] == "b,a" and lines[1] == "2,1"

    def test_empty_rows(self):
        assert exporters.to_csv([]) == ""

    def test_extra_keys_ignored(self):
        csv_text = exporters.to_csv([{"a": 1, "zzz": 9}], columns=["a"])
        assert "zzz" not in csv_text


class TestExports:
    def test_sessions(self, db):
        rows = exporters.export_sessions(db)
        assert len(rows) == 1
        assert rows[0]["student"] == "张三" and rows[0]["messages"] == 2

    def test_applies_no_payload_leak(self, db):
        rows = exporters.export_applies(db)
        assert rows[0]["status"] == "submitted"
        assert "payload" not in rows[0]       # 导出不含申请正文，防敏感外流

    def test_rounds_all_and_filtered(self, db):
        assert len(exporters.export_rounds(db)) == 1
        assert exporters.export_rounds(db, session_id="no_such") == []

    def test_session_markdown(self, db):
        md = exporters.session_markdown(db, "s1")
        assert "会话纪要" in md and "**学生**" in md and "search_policy" in md

    def test_session_markdown_missing(self, db):
        with pytest.raises(ValueError):
            exporters.session_markdown(db, "ghost")
