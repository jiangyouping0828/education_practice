# -*- coding: utf-8 -*-
"""数据导出（exporters）：会话 / 申请单 / 轮次日志导出为 CSV 或 Markdown。

用途：督导汇报、教学抽查、制度优化分析。全部只读，不修改任何数据。
"""

import csv
import io
import sqlite3
from typing import Optional


def _query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def to_csv(rows: list[dict], columns: Optional[list[str]] = None) -> str:
    """把字典列表渲染为 CSV 字符串（UTF-8 with BOM，Excel 直接打开不乱码）。"""
    if not rows:
        return ""
    columns = columns or list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return "\ufeff" + buf.getvalue()


def export_sessions(conn: sqlite3.Connection) -> list[dict]:
    """全部会话概览：归属学生、问答轮数、最后活跃时间。"""
    return _query(conn, """
        SELECT s.id, s.title, COALESCE(u.name, s.user_id) AS student,
               s.created_at, s.last_active_at,
               SUM(CASE WHEN m.role='user' THEN 1 ELSE 0 END) AS questions,
               COUNT(m.id) AS messages
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        LEFT JOIN users u ON u.id = s.user_id
        GROUP BY s.id ORDER BY s.last_active_at DESC""")


def export_applies(conn: sqlite3.Connection) -> list[dict]:
    """全部申请单：类型/状态/创建时间（不含 payload 正文，避免敏感内容外流）。"""
    return _query(conn, """
        SELECT a.id, COALESCE(u.name, a.user_id) AS student, a.apply_type,
               a.status, a.created_at, a.updated_at
        FROM applies a LEFT JOIN users u ON u.id = a.user_id
        ORDER BY a.created_at DESC""")


def export_rounds(conn: sqlite3.Connection, session_id: Optional[str] = None) -> list[dict]:
    """智能体轮次日志：工具调用耗时与状态，可按会话过滤。"""
    where, params = "", ()
    if session_id:
        where, params = " WHERE r.session_id = ?", (session_id,)
    return _query(conn, f"""
        SELECT r.session_id, r.round_no, r.tool_name, r.status,
               r.duration_ms, r.created_at
        FROM agent_rounds r{where} ORDER BY r.session_id, r.round_no""", params)


def session_markdown(conn: sqlite3.Connection, session_id: str) -> str:
    """单会话渲染为 Markdown 对话纪要（附引用来源与轮次统计）。"""
    conn.row_factory = sqlite3.Row
    meta = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not meta:
        raise ValueError(f"会话不存在：{session_id}")
    msgs = _query(conn, "SELECT role, content, citations, created_at FROM messages"
                        " WHERE session_id=? ORDER BY created_at", (session_id,))
    rounds = _query(conn, "SELECT round_no, tool_name, status FROM agent_rounds"
                          " WHERE session_id=? ORDER BY round_no", (session_id,))
    lines = [f"# 会话纪要 {session_id}", "",
             f"- 开始时间：{meta['created_at']}",
             f"- 消息数：{len(msgs)}；工具调用：{len(rounds)}", "", "---", ""]
    for m in msgs:
        who = "学生" if m["role"] == "user" else "助手"
        lines += [f"**{who}**：{m['content']}", ""]
        if m["citations"]:
            lines += [f"> 引用：{m['citations']}", ""]
    if rounds:
        lines += ["## 工具调用轨迹", ""]
        lines += [f"{r['round_no']}. `{r['tool_name']}` → {r['status']}" for r in rounds]
    return "\n".join(lines)
