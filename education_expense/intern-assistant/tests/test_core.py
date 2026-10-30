# -*- coding: utf-8 -*-
"""票据硬闸门对抗测试（与 src/intern_assistant/core 对应）。

覆盖上线检查清单中的安全红线：伪造、篡改、重放、越权、正常链路。
运行：pytest tests/ -v
"""

import json
import os
import sqlite3
import sys
import time

import pytest

# 保证 src 可导入
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.core.app import issue_ticket, verify_ticket, SCHEMA  # noqa: E402


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    yield conn
    conn.close()


PAYLOAD = {"apply_type": "leave", "start_date": "2026-11-02", "end_date": "2026-11-02", "reason": "身体不适就医"}


def test_normal_flow(db):
    """正常链路：签发 → 校验通过并核销。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD) is None
    row = db.execute("SELECT used_at FROM apply_tickets WHERE ticket=?", (t,)).fetchone()
    assert row["used_at"] is not None


def test_forged_ticket(db):
    """伪造票据 → TICKET_INVALID。"""
    assert verify_ticket(db, "deadbeef", "u1", "leave", PAYLOAD) == "TICKET_INVALID"


def test_tampered_payload(db):
    """篡改内容（哪怕一个字）→ PAYLOAD_MISMATCH。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    bad = dict(PAYLOAD, reason="身体不适就医。")   # 多一个句号
    assert verify_ticket(db, t, "u1", "leave", bad) == "PAYLOAD_MISMATCH"


def test_replay_after_consume(db):
    """重放已核销票据 → TICKET_REUSED。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD) is None
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD) == "TICKET_REUSED"


def test_expired_ticket(db):
    """过期票据 → TICKET_EXPIRED。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    db.execute("UPDATE apply_tickets SET expires_at=? WHERE ticket=?", (time.time() - 1, t))
    db.commit()
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD) == "TICKET_EXPIRED"


def test_user_mismatch(db):
    """换用户使用 → TICKET_MISMATCH。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    assert verify_ticket(db, t, "u2", "leave", PAYLOAD) == "TICKET_MISMATCH"


def test_type_mismatch(db):
    """换申请类型使用 → TICKET_MISMATCH。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    assert verify_ticket(db, t, "u1", "transfer", PAYLOAD) == "TICKET_MISMATCH"


def test_missing_required_field(db):
    """缺必填字段的 payload 与签发时不一致 → PAYLOAD_MISMATCH（闸门不猜补）。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    bad = {k: v for k, v in PAYLOAD.items() if k != "reason"}
    assert verify_ticket(db, t, "u1", "leave", bad) == "PAYLOAD_MISMATCH"


def test_precheck_does_not_consume(db):
    """预检（consume=False）不核销：草稿创建阶段可重复预检，确认时才消费。"""
    t = issue_ticket(db, "u1", "leave", PAYLOAD)
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD, consume=False) is None
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD, consume=False) is None
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD, consume=True) is None
    assert verify_ticket(db, t, "u1", "leave", PAYLOAD, consume=True) == "TICKET_REUSED"
