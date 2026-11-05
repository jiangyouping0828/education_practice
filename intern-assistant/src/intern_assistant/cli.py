# -*- coding: utf-8 -*-
"""命令行入口（cli）

把散落在 scripts 里的运维动作统一成一条命令：

    PYTHONPATH=src python -m intern_assistant.cli <子命令>

子命令：
    init-db     初始化数据库（建表 + 种子账号 + 示例制度）
    eval        离线评测：静态审计 + mock 全流程跑 30 条用例
    purge       清理过期令牌/日志/票据（--days 保留期，--exec 真删，默认 dry-run）
    backup      备份数据库到 data/runtime/backups（--keep 保留份数）
    export      导出数据（sessions/applies/rounds，CSV）
    session     单会话 Markdown 纪要
"""

import argparse
import os
import shutil
import sqlite3
import sys
import time

# 保证未安装包时也能运行（与 main.py 同策略）
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from intern_assistant.core import maintenance  # noqa: E402


def _db_path() -> str:
    from intern_assistant.core.app import DB_PATH
    return DB_PATH


def cmd_init_db(_args) -> int:
    from intern_assistant.core.app import init_db
    init_db()
    print(f"[OK] 数据库就绪：{_db_path()}")
    return 0


def cmd_eval(args) -> int:
    """离线评测：审计用例集 + 以"期望行为反推"的 mock ask_fn 走全流程打分。

    离线模式验证的是"评测管线与用例集本身"，模型行为评测仍需 live 模式
    （docs/eval.md 第 3 节）。这里保证 30 条用例随时可机审。
    """
    from intern_assistant.evaluation import evaluate, load_cases, render_markdown
    cases = load_cases(args.cases)

    def mock_ask(case: dict) -> dict:
        # mock 策略：制度类/多轮回答带引用；陷阱与违规类按 expected_tools 原样回放。
        # 引用后缀让"引用来源"维度在离线回放下恒真——真实模型行为需 live 评测。
        answer = "（离线回放）"
        if case["category"] in ("制度问答", "制度问答-陷阱", "多轮上下文"):
            answer += " 制度文件中未找到相关规定 【片段1·实习制度示例.md】"
        elif case["category"] == "违规意图":
            answer = "不能协助，请按规定补交材料并联系企业导师说明情况。"
        return {"tools": list(case["expected_tools"]), "answer": answer}

    report = evaluate(cases, mock_ask)
    print(render_markdown(report, title=f"离线评测报告（{os.path.basename(args.cases)}）"))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(render_markdown(report, title="离线评测报告"))
        print(f"[OK] 报告已写入 {args.out}")
    return 0 if report["total_passed"] == report["total"] else 1


def cmd_purge(args) -> int:
    stats = maintenance.run_maintenance(_db_path(), retention_days=args.days,
                                        dry_run=not args.exec)
    mode = "DRY-RUN（预览，未删除）" if not args.exec else "已执行删除"
    print(f"维护模式：{mode}")
    print(f"过期令牌：{stats['expired_tokens']} 条")
    print(f"超期日志：{stats['old_logs']}（保留 {args.days} 天）")
    print(f"过期票据：{stats['expired_tickets']} 条")
    if not args.exec:
        print("确认无误后追加 --exec 真正执行。")
    return 0


def cmd_backup(args) -> int:
    src = _db_path()
    backup_dir = os.path.join(os.path.dirname(src), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    # 文件名含毫秒：同秒多次备份不重名
    stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
    dst = os.path.join(backup_dir, f"chat_{stamp}.db")
    shutil.copy2(src, dst)
    # 按保留份数清理旧备份
    backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("chat_"))
    for old in backups[:max(0, len(backups) - args.keep)]:
        os.remove(os.path.join(backup_dir, old))
    print(f"[OK] 已备份：{dst}（保留最近 {args.keep} 份）")
    return 0


def cmd_export(args) -> int:
    from intern_assistant import exporters
    conn = sqlite3.connect(_db_path())
    try:
        rows = {"sessions": exporters.export_sessions,
                "applies": exporters.export_applies,
                "rounds": exporters.export_rounds}[args.what](conn)
    finally:
        conn.close()
    csv_text = exporters.to_csv(rows)
    if not csv_text:
        print("[WARN] 无数据可导出")
        return 1
    out = args.out or f"export_{args.what}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text)
    print(f"[OK] 导出 {len(rows)} 行 → {out}")
    return 0


def cmd_session(args) -> int:
    from intern_assistant import exporters
    conn = sqlite3.connect(_db_path())
    try:
        md = exporters.session_markdown(conn, args.session_id)
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 1
    finally:
        conn.close()
    out = args.out or f"session_{args.session_id}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[OK] 纪要已写入 {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="intern-assistant", description="实习管理与教学助手运维命令行")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="初始化数据库").set_defaults(func=cmd_init_db)

    pe = sub.add_parser("eval", help="离线评测 30 条用例")
    pe.add_argument("--cases", default=os.path.join(SRC, "..", "data", "eval_cases.json"))
    pe.add_argument("--out", default="", help="评测报告输出路径（可选）")
    pe.set_defaults(func=cmd_eval)

    pp = sub.add_parser("purge", help="清理过期令牌/日志/票据（默认 dry-run）")
    pp.add_argument("--days", type=int, default=maintenance.DEFAULT_RETENTION_DAYS)
    pp.add_argument("--exec", action="store_true", help="真正执行删除（默认仅预览）")
    pp.set_defaults(func=cmd_purge)

    pb = sub.add_parser("backup", help="备份数据库")
    pb.add_argument("--keep", type=int, default=10, help="保留最近 N 份")
    pb.set_defaults(func=cmd_backup)

    px = sub.add_parser("export", help="导出 sessions/applies/rounds 为 CSV")
    px.add_argument("what", choices=["sessions", "applies", "rounds"])
    px.add_argument("--out", default="")
    px.set_defaults(func=cmd_export)

    ps = sub.add_parser("session", help="导出单会话 Markdown 纪要")
    ps.add_argument("session_id")
    ps.add_argument("--out", default="")
    ps.set_defaults(func=cmd_session)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
