# -*- coding: utf-8 -*-
"""身份与数据隔离测试：学生各看各的，管理员只能看不能替学生操作。

依赖：fastapi/httpx（TestClient）。运行：pytest tests/ -v
测试库由 conftest.py 统一切到临时文件（IMS_DB_PATH），不污染真实数据。
"""

import os
import sqlite3
import sys
import tempfile

import pytest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

TMP_DB = os.environ["IMS_DB_PATH"]

from fastapi.testclient import TestClient  # noqa: E402

from intern_assistant.core import app as app_module  # noqa: E402


@pytest.fixture(scope="module")
def client():
    app_module.init_db()
    with TestClient(app_module.app) as c:
        yield c


def _login(client, username, password, kind="student"):
    path = "/student/login" if kind == "student" else "/login"
    return client.post(path, data={"username": username, "password": password},
                       follow_redirects=False)


def test_anonymous_index_redirects_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/student/login"


def test_anonymous_api_unauthorized(client):
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/chat", json={"question": "请假流程"}).status_code == 401


def test_student_login_identity(client):
    _login(client, "20230101", "123456")
    me = client.get("/api/me").json()
    assert me["student_no"] == "20230101"
    assert me["name"] == "张三"


def test_sessions_are_isolated_between_students(client):
    """核心用例：A 的会话 B 读不到、也续不上。"""
    a = TestClient(app_module.app)
    _login(a, "20230101", "123456")
    with sqlite3.connect(TMP_DB) as db:
        db.row_factory = sqlite3.Row
        sid = "s_test_" + os.urandom(4).hex()
        db.execute("INSERT INTO sessions (id,title,user_id,created_at,last_active_at)"
                   " VALUES (?,?,?,?,?)", (sid, "测试会话", "u_stu_01", 0, 0))
        db.commit()

    b = TestClient(app_module.app)
    _login(b, "20230102", "123456")
    assert b.get(f"/api/sessions/{sid}/messages").status_code == 403
    assert b.post("/api/chat", json={"session_id": sid, "question": "继续"}).status_code == 403
    # 本人可读
    assert a.get(f"/api/sessions/{sid}/messages").status_code == 200


def test_admin_cookie_cannot_act_as_student(client):
    admin = TestClient(app_module.app)
    _login(admin, "admin", "admin123", kind="admin")
    assert admin.get("/admin/records").status_code == 200
    assert admin.get("/api/me").status_code == 401      # 管理员令牌与学生令牌分表


def test_admin_cannot_confirm_student_draft(client):
    """管理员无学生身份 → 无法代替学生按下确认键。"""
    admin = TestClient(app_module.app)
    _login(admin, "admin", "admin123", kind="admin")
    r = admin.post("/api/draft/any_draft_id/confirm")
    assert r.status_code == 401


def test_admin_session_view_writes_access_log(client):
    admin = TestClient(app_module.app)
    _login(admin, "admin", "admin123", kind="admin")
    with sqlite3.connect(TMP_DB) as db:
        db.row_factory = sqlite3.Row
        sid = "s_audit_" + os.urandom(4).hex()
        db.execute("INSERT INTO sessions (id,title,user_id,created_at,last_active_at)"
                   " VALUES (?,?,?,?,?)", (sid, "审计用例", "u_stu_01", 0, 0))
        db.commit()
    assert admin.get(f"/admin/sessions/{sid}").status_code == 200
    with sqlite3.connect(TMP_DB) as db:
        n = db.execute("SELECT COUNT(*) FROM admin_access_log WHERE target_session=?",
                       (sid,)).fetchone()[0]
    assert n == 1
