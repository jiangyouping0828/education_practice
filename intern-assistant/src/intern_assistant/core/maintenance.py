# -*- coding: utf-8 -*-
"""数据维护任务（core.maintenance）

落地《上线前检查清单》的日志保留策略：
- 令牌清理：过期登录令牌（12h TTL）及时出库；
- 日志保留：agent_rounds / tool_audit_log / admin_access_log 超过保留期归档删除；
- 票据清理：过期未用票据删除；
- 库优化：VACUUM 回收空间。

所有删除操作支持 dry_run：只统计不执行，供运维核对后再跑。
"""

import sqlite3
import time

RETENTION_TABLES = {
    "agent_rounds": "created_at",
    "tool_audit_log": "created_at",
    "admin_access_log": "created_at",
}
DEFAULT_RETENTION_DAYS = 180


def purge_expired_tokens(conn: sqlite3.Connection, dry_run: bool = True) -> int:
    """删除过期登录令牌（管理员与学生两张表），返回受影响行数；缺表记 0 跳过。"""
    now = time.time()
    total = 0
    for table, column in (("admin_tokens", "expires"), ("student_tokens", "expires")):
        try:
            n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} < ?", (now,)).fetchone()[0]
        except sqlite3.OperationalError:
            continue
        if not dry_run and n:
            conn.execute(f"DELETE FROM {table} WHERE {column} < ?", (now,))
        total += n
    if not dry_run:
        conn.commit()
    return total


def purge_old_logs(conn: sqlite3.Connection, days: int = DEFAULT_RETENTION_DAYS,
                   dry_run: bool = True) -> dict[str, int]:
    """按保留期清理三类运行日志，返回 {表名: 将删除行数}。"""
    cutoff = time.time() - days * 86400
    stats: dict[str, int] = {}
    for table, column in RETENTION_TABLES.items():
        try:
            n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} < ?", (cutoff,)).fetchone()[0]
        except sqlite3.OperationalError:
            stats[table] = -1          # 表不存在（旧库未升级），跳过
            continue
        if not dry_run and n:
            conn.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))
        stats[table] = n
    if not dry_run:
        conn.commit()
    return stats


def purge_expired_tickets(conn: sqlite3.Connection, dry_run: bool = True) -> int:
    """清理已过期且未使用的校验票据（已核销的保留作审计证据）；缺表记 0。"""
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM apply_tickets WHERE expires_at < ? AND used_at IS NULL",
            (time.time(),)).fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    if not dry_run and n:
        conn.execute(
            "DELETE FROM apply_tickets WHERE expires_at < ? AND used_at IS NULL",
            (time.time(),))
        conn.commit()
    return n


def optimize_db(conn: sqlite3.Connection) -> None:
    """VACUUM 回收删除后的空间（维护窗口执行，量大时耗时数秒）。"""
    conn.execute("VACUUM")
    conn.commit()


def run_maintenance(db_path: str, retention_days: int = DEFAULT_RETENTION_DAYS,
                    dry_run: bool = True) -> dict:
    """一条命令完成全部清理。返回统计字典，可直接打印给运维。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            "dry_run": dry_run,
            "expired_tokens": purge_expired_tokens(conn, dry_run),
            "old_logs": purge_old_logs(conn, retention_days, dry_run),
            "expired_tickets": purge_expired_tickets(conn, dry_run),
        }
    finally:
        conn.close()
