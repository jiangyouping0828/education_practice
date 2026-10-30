# -*- coding: utf-8 -*-
"""
阶段 2：员工问答 Web 入口（FastAPI + SQLite + SSE 流式）
=========================================================
对应四层架构：入口层（index.html）→ 服务层（本文件的路由）
             → 编排层（复用阶段 1 的切片/检索/提示词模块）→ 数据层（SQLite）

启动：uvicorn app:app --port 8000   然后浏览器打开 http://127.0.0.1:8000

接口约定：所有非流式接口出错时统一返回 {"code": "...", "message": "中文描述"}；
SSE 流内错误用 event: error 帧收尾（流已开始，HTTP 状态码无法再改）。
"""

import json
import hashlib
import os
import secrets
import sqlite3
import time
import urllib.parse
import uuid
from typing import Optional

import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag_prototype import (        # ★ 复用阶段 1 核心模块
    CONFIG, _load_dotenv, chunk_text, llm_embed,
)

_load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chat.db")
DOC_PATH = CONFIG["doc_path"]

# ---------------------------------------------------------------------------
# 数据层：SQLite 建表（沿用阶段 1 表结构；users 本期不启用，结构预留）
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee',
    org_id TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT,                    -- 取首问前 20 字，会话列表用
    user_id TEXT,                  -- 本期填 'local'
    created_at REAL, last_active_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,            -- user / assistant
    content TEXT NOT NULL,
    citations TEXT,                -- JSON 数组：[{rank,document,section,excerpt,score}]
    created_at REAL
);
CREATE TABLE IF NOT EXISTS kb_documents (
    id TEXT PRIMARY KEY, title TEXT UNIQUE NOT NULL, file_path TEXT,
    status TEXT DEFAULT 'indexed', version INTEGER DEFAULT 1,
    uploaded_by TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS kb_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kb_documents(id),
    section TEXT,                  -- 所属章节标题（引用展示用）
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    embedding BLOB,                -- float32 向量二进制；向量化失败时为 NULL
    token_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
CREATE TABLE IF NOT EXISTS admin_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires REAL NOT NULL
);
-- ====== 阶段 4：智能体化新增表 ======
-- 申请单（请假 leave / 换岗 transfer）；payload 为申请内容 JSON
CREATE TABLE IF NOT EXISTS applies (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    user_id TEXT NOT NULL,
    apply_type TEXT NOT NULL,          -- leave / transfer
    payload TEXT NOT NULL,             -- JSON：申请字段
    status TEXT NOT NULL DEFAULT 'submitted',  -- submitted / approved / rejected（签核链后续扩展）
    approval_route TEXT,               -- 审批路径（依据制度生成）
    ticket TEXT,                       -- 创建时核销的校验票据（审计可溯）
    created_at REAL, submitted_at REAL
);
-- 校验票据：validate 通过才签发；create 时核销（防绕过校验的硬闸门）
CREATE TABLE IF NOT EXISTS apply_tickets (
    ticket TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    apply_type TEXT NOT NULL,
    payload TEXT NOT NULL,             -- 校验时的申请内容原文（提示词回注，保证逐字一致）
    payload_hash TEXT NOT NULL,        -- 校验时内容的哈希：create 内容改动一个字即失配
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    used_at REAL                       -- 非空 = 已核销，禁止复用
);
-- 工具调用审计日志：每次调用的顺序与结果，违规可回溯
CREATE TABLE IF NOT EXISTS tool_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT, tool_name TEXT NOT NULL,
    args_digest TEXT,                  -- 参数摘要（不存全文，日志最小化）
    result_code TEXT,                  -- ok / 具体错误码
    created_at REAL
);
-- ====== 阶段 5：Agent Harness 轮次日志（供执行轨迹分析）======
-- 每轮决策一行：模型选了什么工具、参数、耗时、结果摘要、最终走向
CREATE TABLE IF NOT EXISTS agent_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    round_no INTEGER NOT NULL,         -- 第几轮（1 起始；final_answer 行也占一轮）
    tool_name TEXT,                    -- 模型决策调用的工具；最终回答记 final_answer；空转记 none
    args_json TEXT,                    -- 工具参数原文（分析用；敏感字段应在生产脱敏）
    duration_ms INTEGER,               -- 该轮总耗时（LLM 决策 + 工具执行）
    result_digest TEXT,                -- 结果摘要（前 200 字符）
    status TEXT,                       -- ok / 错误码 / intercepted（被人工确认中断）
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_rounds_session ON agent_rounds(session_id, round_no);
"""


def get_db() -> sqlite3.Connection:
    """每个请求独立连接（SQLite 写并发弱，原型阶段够用；Web 化后期换 PostgreSQL）。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pwd(pwd: str) -> str:
    """密码哈希（原型阶段用固定盐 sha256；生产环境应换 bcrypt/argon2）。"""
    return hashlib.sha256(("ims_" + pwd).encode()).hexdigest()


def ingest_document(db: sqlite3.Connection, title: str, text: str) -> dict:
    """制度文档入库：切片 → 向量化（失败降级）→ 写 kb_documents / kb_chunks。

    供启动导入和管理员上传共用（★阶段1 切片模块复用点）。
    """
    doc_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO kb_documents (id, title, status, created_at) VALUES (?,?,?,?)",
        (doc_id, title, "indexed", time.time()),
    )
    chunks = chunk_text(text, CONFIG["chunk_size"])
    vectors = None
    try:
        vectors = np.array(llm_embed(chunks), dtype="float32")
    except Exception as e:
        print(f"[知识库] 向量化失败，BM25 降级：{e}")
    for i, ctext in enumerate(chunks):
        emb = vectors[i].tobytes() if vectors is not None else None
        section = ctext.split("】")[0].lstrip("【") if "】" in ctext else ""
        db.execute(
            "INSERT INTO kb_chunks (id, document_id, section, chunk_text, chunk_index, embedding, token_count)"
            " VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), doc_id, section, ctext, i, emb, len(ctext)),
        )
    return {"doc_id": doc_id, "chunks": len(chunks), "with_vectors": vectors is not None}


def init_db() -> None:
    """建表 + 种子数据：管理员账号 + 首次启动导入示例制度。"""
    with get_db() as db:
        db.executescript(SCHEMA)
        # 管理员种子账号（首次启动创建；正式环境应首登强制改密）
        if not db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            db.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?,?,?,?,?)",
                ("u_admin", "admin", hash_pwd("admin123"), "admin", time.time()),
            )
        if db.execute("SELECT COUNT(*) AS n FROM kb_chunks").fetchone()["n"] > 0:
            return
        result = ingest_document(db, os.path.basename(DOC_PATH),
                                 open(DOC_PATH, encoding="utf-8").read())
        print(f"[知识库] 已导入 {result['chunks']} 个片段"
              f"（{'含向量' if result['with_vectors'] else 'BM25 降级'}）")


# ---------------------------------------------------------------------------
# 编排层：DB 版混合检索器（检索逻辑复用阶段 1，存储从 FAISS 文件换成 SQLite BLOB）
# ---------------------------------------------------------------------------

class DBRetriever:
    """启动时把全部片段与向量读进内存；原型规模（几千片内）性能足够。

    Web 规模化路径：换 pgvector 做库内检索，本类只改数据来源，接口不变。
    """

    def __init__(self):
        from rank_bm25 import BM25Okapi
        import jieba
        with get_db() as db:
            rows = db.execute(
                "SELECT c.id, c.section, c.chunk_text, c.embedding, d.title AS doc_title"
                " FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id"
            ).fetchall()
        self.items = [dict(r) for r in rows]
        self.chunks = [r["chunk_text"] for r in self.items]
        self.bm25 = BM25Okapi([list(jieba.cut(c)) for c in self.chunks]) if self.chunks else None
        # 还原向量矩阵（BLOB → float32）；存在 NULL 时整体降级
        embs = [r["embedding"] for r in self.items]
        self.matrix = None
        if self.chunks and all(e is not None for e in embs):
            self.matrix = np.frombuffer(b"".join(embs), dtype="float32").reshape(len(embs), -1)
            import faiss
            faiss.normalize_L2(self.matrix)
            self.index = faiss.IndexFlatIP(self.matrix.shape[1])
            self.index.add(self.matrix)
        else:
            self.index = None

    @staticmethod
    def _minmax(s: np.ndarray) -> np.ndarray:
        lo, hi = s.min(), s.max()
        return (s - lo) / (hi - lo) if hi > lo else np.zeros_like(s)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """混合检索；与阶段 1 同一套融合逻辑（★核心模块③），返回带文档信息的片段。"""
        import jieba
        if not self.chunks:
            return []
        bm = self.bm25.get_scores(list(jieba.cut(query)))
        if self.index is None:
            final = self._minmax(bm)
        else:
            import faiss
            qv = np.array([llm_embed([query])[0]], dtype="float32")
            faiss.normalize_L2(qv)
            d, i = self.index.search(qv, len(self.chunks))
            vs = np.zeros(len(self.chunks)); vs[i[0]] = d[0]
            final = CONFIG["vector_weight"] * self._minmax(vs) + CONFIG["bm25_weight"] * self._minmax(bm)
        top = np.argsort(final)[::-1][:top_k]
        return [
            {"rank": r + 1, "chunk_id": self.items[idx]["id"],
             "document": self.items[idx]["doc_title"], "section": self.items[idx]["section"],
             "chunk_text": self.chunks[idx], "excerpt": self.chunks[idx][:80],
             "score": round(float(final[idx]), 3)}
            for r, idx in enumerate(top)
        ]


RETRIEVER: DBRetriever = None   # 启动时初始化

# ---------------------------------------------------------------------------
# 提示词：制度片段 + 最近 6 轮历史（★核心模块④ 的 Web 版）
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    f"你是《实习管理制度》的问答助手。以下规则优先级最高，逐条强制执行：\n"
    "1. 只依据本次提供的制度片段回答，禁止使用片段之外的任何知识；\n"
    "2. 制度片段中没有对应条款的，直接输出：「制度文件中未找到相关规定」，不作任何推测；\n"
    "3. 每一条结论都必须附带文档名称作为引用来源，格式：末尾标注【片段N·文档名】；\n"
    "4. 绝对不凭空编造实习时长、评分标准、审批流程、材料要求等管理条款；\n"
    "5. 历史对话仅用于理解上下文，不要引用历史里可能过期的内容。"
)

MAX_QUESTION_LEN = 500      # 问题长度上限
HISTORY_ROUNDS = 6          # 携带最近 6 轮历史 = 12 条消息


def build_user_prompt(question: str, hits: list[dict], history: list[dict]) -> str:
    """拼装：制度片段 + 最近历史 + 本轮问题。"""
    ctx = "\n\n".join(
        f"片段{h['rank']}（{h['document']}·{h['section']}）：{h['chunk_text']}" for h in hits
    )
    hist = "\n".join(f"{'员工' if m['role'] == 'user' else '助手'}：{m['content'][:200]}"
                     for m in history[-HISTORY_ROUNDS * 2:])
    parts = []
    if hist:
        parts.append(f"【最近对话】\n{hist}")
    parts.append(f"【制度片段】\n{ctx}")
    parts.append(f"【员工问题】{question}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM 流式调用（★核心模块① 的流式版：只加 stream 参数，供应商仍可配置）
# ---------------------------------------------------------------------------

def stream_llm(system: str, user: str):
    """逐段产出 LLM 回答文本；失败抛 HTTPError 由上层转成 error 帧。"""
    resp = requests.post(
        f"{CONFIG['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {CONFIG['api_key']}"},
        json={"model": CONFIG["chat_model"], "stream": True,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
              "temperature": 0.2},
        stream=True, timeout=(10, 120),
    )
    resp.raise_for_status()
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            piece = json.loads(payload)["choices"][0]["delta"].get("content")
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
        if piece:
            yield piece


# ===========================================================================
# 阶段 4：智能体层（Function Calling）
# 设计原则：提示词只能"劝"，Schema 让模型"组不出"，服务端票据闸门才能"拦"。
# 调用顺序约束的硬保障 = 校验票据（单次有效 / 10 分钟过期 / 内容哈希绑定）。
# ===========================================================================

# ---- 业务规则引擎（条款出处 = 示例制度文档，制度更新由管理员维护文档）----
# required: (字段名, 中文标签, 最小长度)；min_len=0 表示只要求非空
APPLY_RULES = {
    "leave": {
        "name": "请假申请",
        "required": [("start_date", "开始日期", 0), ("end_date", "结束日期", 0), ("reason", "请假事由", 4)],
        # 依据《实习制度示例.md·考勤与请假》：1~3 天导师审批，超 3 天报学校教师
        "route": lambda days: ("企业导师审批" if days <= 3 else "企业导师审批 → 学校实习指导教师审批"),
        "source": "实习制度示例.md·考勤与请假",
    },
    "transfer": {
        "name": "换岗申请",
        "required": [("current_position", "现岗位", 0), ("target_position", "目标岗位", 0),
                     ("reason", "换岗原因", 4), ("expected_date", "期望生效日期", 0)],
        # 依据《实习制度示例.md·换岗流程》：换岗自备案完成之日起生效
        "route": lambda days: "企业导师同意 → 学校实习指导教师备案",
        "source": "实习制度示例.md·换岗流程",
    },
    "weekly_report": {
        "name": "实习周报",
        # 依据《实习制度示例.md·周报填报规范》：总结≥30字、计划≥10字
        "required": [("week_number", "周次", 0), ("work_summary", "本周工作总结", 30),
                     ("next_plan", "下周工作计划", 10)],
        "route": lambda days: "企业导师评阅",
        "source": "实习制度示例.md·周报填报规范",
    },
    "daily_log": {
        "name": "实习日志",
        # 依据《实习制度示例.md·实习日志提交标准》：内容≥50字、工时≤8
        "required": [("log_date", "日期", 0), ("content", "当日实习内容", 50),
                     ("duration_hours", "当日工时", 0)],
        "route": lambda days: "企业导师月度核查签字",
        "source": "实习制度示例.md·实习日志提交标准",
    },
}


def _days_between(d1: str, d2: str) -> Optional[int]:
    """计算两个 YYYY-MM-DD 日期的间隔天数；格式非法返回 None。"""
    import datetime
    try:
        a = datetime.date.fromisoformat(d1)
        b = datetime.date.fromisoformat(d2)
        return (b - a).days + 1
    except ValueError:
        return None


def validate_payload(apply_type: str, payload: dict) -> dict:
    """纯规则校验（模型只负责收集字段，判定权在代码）：返回 valid / missing / warnings。

    校验维度：必填齐备 → 最小字数（防"内容空洞"）→ 类型专属规则（日期/工时上限）。
    """
    rule = APPLY_RULES.get(apply_type)
    if not rule:
        return {"valid": False, "missing": [],
                "message": f"不支持的申请类型：{apply_type}（可选：leave 请假 / transfer 换岗 / weekly_report 周报 / daily_log 日志）"}
    missing, warnings = [], []
    for key, label, min_len in rule["required"]:
        val = str(payload.get(key) or "").strip()
        if not val:
            missing.append(label)
        elif min_len and len(val) < min_len:
            missing.append(f"{label}（不少于 {min_len} 字，当前 {len(val)} 字）")
    if apply_type == "leave" and not missing:
        days = _days_between(payload["start_date"], payload["end_date"])
        if days is None:
            missing.append("日期格式（应为 YYYY-MM-DD）")
        elif days <= 0:
            missing.append("结束日期（不能早于开始日期）")
        elif days > 30:
            return {"valid": False, "missing": missing,
                    "message": f"请假 {days} 天超出单次上限 30 天（依据：{rule['source']}），超出部分需另行办理"}
    if apply_type == "daily_log" and not missing:
        try:
            hours = float(payload["duration_hours"])
            if not (0 < hours <= 8):
                missing.append(f"当日工时（须在 0~8 之间，当前 {payload['duration_hours']}，依据：{rule['source']}）")
        except (TypeError, ValueError):
            missing.append("当日工时（应为数字）")
    if not missing:
        days = _days_between(payload.get("start_date", "2000-01-01"),
                             payload.get("end_date", "2000-01-02")) or 1
        return {"valid": True, "missing": [], "warnings": warnings,
                "route": rule["route"](days), "source": rule["source"]}
    return {"valid": False, "missing": missing,
            "message": "存在不合规项：" + "、".join(missing) + "。请向用户追问或说明，禁止代填。"}


def issue_ticket(db, user_id: str, apply_type: str, payload: dict) -> str:
    """校验通过 → 签发票据：绑定用户 + 类型 + 内容哈希，10 分钟单次有效。"""
    payload_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    ticket = secrets.token_hex(16)
    now = time.time()
    db.execute("INSERT INTO apply_tickets (ticket,user_id,apply_type,payload,payload_hash,issued_at,expires_at)"
               " VALUES (?,?,?,?,?,?,?)",
               (ticket, user_id, apply_type,
                json.dumps(payload, ensure_ascii=False, sort_keys=True), payload_hash, now, now + 600))
    return ticket


def verify_ticket(db, ticket: str, user_id: str, apply_type: str, payload: dict,
                  consume: bool = True) -> Optional[str]:
    """票据校验（create/confirm 前的硬闸门）：返回 None=通过；否则返回拒绝原因错误码。

    consume=True 时核销（单次有效）；草稿创建阶段用 consume=False 只预检不核销，
    真正核销发生在学生点击"确认提交"时——保证"确认"才是唯一消费点。
    四种拒绝：不存在/伪造 TICKET_INVALID；过期 TICKET_EXPIRED；
    已用过 TICKET_REUSED；内容与校验时不一致 PAYLOAD_MISMATCH。
    """
    row = db.execute("SELECT * FROM apply_tickets WHERE ticket=?", (ticket,)).fetchone()
    if not row:
        return "TICKET_INVALID"
    if row["expires_at"] < time.time():
        return "TICKET_EXPIRED"
    if row["used_at"] is not None:
        return "TICKET_REUSED"
    if row["user_id"] != user_id or row["apply_type"] != apply_type:
        return "TICKET_MISMATCH"
    payload_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if row["payload_hash"] != payload_hash:
        return "PAYLOAD_MISMATCH"
    if consume:
        db.execute("UPDATE apply_tickets SET used_at=? WHERE ticket=?", (time.time(), ticket))
    return None


def audit_tool(db, session_id: str, tool_name: str, args: dict, result_code: str):
    """工具调用审计：参数只存摘要（日志最小化），违规可回溯。"""
    db.execute("INSERT INTO tool_audit_log (session_id,tool_name,args_digest,result_code,created_at)"
               " VALUES (?,?,?,?,?)",
               (session_id, tool_name,
                hashlib.sha256(json.dumps(args, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16],
                result_code, time.time()))


# ---- 工具注册表（OpenAI function calling 规范；validation_ticket 为 create 的必填参数）----
TOOLS = [
    {"type": "function", "function": {
        "name": "search_policy",
        "description": "检索实习管理制度条文。回答任何制度类问题（签到要求/能请几天/填报规范/提交标准）之前必须先调用本工具；检索不到就如实告知用户制度未覆盖，禁止凭记忆回答。纯制度问答只调本工具即可，不要调用其他工具。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "检索关键词或问题"},
        }, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_intern_context",
        "description": "查询当前学生自己的实习上下文（岗位、导师、批次、状态）。帮用户起草申请/周报/日志前先调用，避免让用户重复输入已知信息。",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "validate_apply_material",
        "description": "校验申请/周报/日志材料是否齐备合规。校验通过会返回 validation_ticket（创建草稿必须凭此票据）；不通过返回不合规项列表，此时唯一正确动作是向用户追问或说明，禁止代填。若用户只是问“我这份材料符合标准吗”，校验完直接给结论即可，不要创建草稿。",
        "parameters": {"type": "object", "properties": {
            "apply_type": {"type": "string", "enum": ["leave", "transfer", "weekly_report", "daily_log"],
                           "description": "leave=请假 / transfer=换岗 / weekly_report=周报 / daily_log=实习日志"},
            "payload": {"type": "object", "description": "材料字段。leave: start_date,end_date,reason；transfer: current_position,target_position,reason,expected_date；weekly_report: week_number,work_summary(≥30字),next_plan(≥10字)；daily_log: log_date,content(≥50字),duration_hours(0~8)"},
        }, "required": ["apply_type", "payload"]}}},
    {"type": "function", "function": {
        "name": "create_intern_draft",
        "description": "创建实习申报草稿（请假/换岗/周报/日志）。凭 validate_apply_material 返回的 validation_ticket 调用；系统会自动拦截本工具：先向学生流式展示草稿全文等待确认，学生确认后才会真正提交。调用前请先把草稿要点向用户复述一遍。",
        "parameters": {"type": "object", "properties": {
            "apply_type": {"type": "string", "enum": ["leave", "transfer", "weekly_report", "daily_log"]},
            "payload": {"type": "object", "description": "材料字段，与校验时完全一致"},
            "validation_ticket": {"type": "string", "description": "validate_apply_material 返回的票据原文"},
        }, "required": ["apply_type", "payload", "validation_ticket"]}}},
    {"type": "function", "function": {
        "name": "query_my_applies",
        "description": "查询当前学生自己已提交的申请单/周报/日志及状态。",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["pending_confirm", "submitted", "approved", "rejected"],
                       "description": "可选状态过滤"},
        }}}},
]


def execute_tool(name: str, args: dict, session_id: str, user_id: str) -> tuple[dict, list]:
    """工具执行器：所有副作用集中在这里，顺序约束全部由服务端强制。

    返回 (工具结果dict, SSE事件列表)。SSE 事件用于前端展示执行进度与申请卡片。
    """
    events = []
    with get_db() as db:
        try:
            if name == "search_policy":
                hits = RETRIEVER.search(args.get("query", ""), CONFIG["top_k"])
                sources = [{"rank": h["rank"], "document": h["document"], "section": h["section"],
                            "excerpt": h["excerpt"], "score": h["score"]} for h in hits]
                events.append(sse("sources", {"sources": sources}))
                audit_tool(db, session_id, name, args, "ok")
                return {"hits": [{"document": h["document"], "section": h["section"],
                                  "chunk_text": h["chunk_text"]} for h in hits]}, events

            if name == "get_intern_context":
                # 原型阶段单用户 mock：正式版按登录身份查主数据（岗位/导师/批次版本化关联）
                ctx = {"student": "当前用户", "major": "机电一体化", "batch": "2026 春季批次",
                       "position": "设备点检助理", "mentor": "王工（企业导师）",
                       "school_teacher": "李老师（实习指导教师）", "status": "在岗"}
                audit_tool(db, session_id, name, args, "ok")
                return ctx, events

            if name == "validate_apply_material":
                apply_type, payload = args.get("apply_type", ""), args.get("payload", {})
                result = validate_payload(apply_type, payload)
                if result["valid"]:
                    result["validation_ticket"] = issue_ticket(db, user_id, apply_type, payload)
                    result["ticket_note"] = "票据 10 分钟内有效且只能用一次；创建申请时必须原文携带"
                audit_tool(db, session_id, name, {"apply_type": apply_type},
                           "ok" if result["valid"] else "MISSING_FIELDS")
                return result, events

            if name == "create_intern_draft":
                """⚠️ 本工具实际不由执行器直接执行：AgentHarness 在调用前强制拦截，
                把草稿内容流式发给学生确认。此分支仅作为兜底（万一被直接调用，
                也只做预检与草稿落库，不产生提交效力）。"""
                apply_type, payload = args.get("apply_type", ""), args.get("payload", {})
                ticket = args.get("validation_ticket", "")
                # ---- 硬闸门预检（不核销；核销发生在学生确认时）----
                deny = verify_ticket(db, ticket, user_id, apply_type, payload, consume=False)
                if deny:
                    audit_tool(db, session_id, name, {"apply_type": apply_type}, deny)
                    return {"error": deny, "message": {
                        "TICKET_INVALID": "校验票据无效（可能为编造）。必须先调用 validate_apply_material 获取",
                        "TICKET_EXPIRED": "票据已过期，请重新调用 validate_apply_material",
                        "TICKET_REUSED": "票据已被使用，请重新校验",
                        "TICKET_MISMATCH": "票据与申请类型或用户不匹配",
                        "PAYLOAD_MISMATCH": "草稿内容与校验时不一致（哪怕改一个字也不行），请重新校验",
                    }.get(deny, "票据校验失败")}, events
                rule = APPLY_RULES[apply_type]
                apply_id = "d_" + uuid.uuid4().hex[:10]
                db.execute("INSERT INTO applies (id,session_id,user_id,apply_type,payload,status,approval_route,ticket,created_at)"
                           " VALUES (?,?,?,?,?,?,?,?,?)",
                           (apply_id, session_id, user_id, apply_type,
                            json.dumps(payload, ensure_ascii=False), "pending_confirm",
                            rule["route"](1), ticket, time.time()))
                audit_tool(db, session_id, name, {"apply_type": apply_type}, "draft_pending")
                return {"draft_id": apply_id, "status": "pending_confirm",
                        "note": "草稿已创建并等待学生确认；学生确认后系统自动提交"}, events

            if name == "query_my_applies":
                status = args.get("status")
                sql = "SELECT id, apply_type, payload, status, approval_route, submitted_at FROM applies WHERE user_id=?"
                params: list = [user_id]
                if status:
                    sql += " AND status=?"
                    params.append(status)
                rows = db.execute(sql + " ORDER BY created_at DESC LIMIT 20", params).fetchall()
                audit_tool(db, session_id, name, {"status": status}, "ok")
                return {"applies": [dict(r) for r in rows]}, events

            audit_tool(db, session_id, name, args, "UNKNOWN_TOOL")
            return {"error": "UNKNOWN_TOOL", "message": f"未知工具：{name}"}, events
        except Exception as e:
            audit_tool(db, session_id, name, args, f"EXC:{e.__class__.__name__}")
            return {"error": "TOOL_FAILED", "message": f"工具执行异常：{e}"}, events


# ---- 智能体系统提示词：问答纪律 + 工具铁律 ----
SYSTEM_PROMPT_AGENT = (
    "你是《实习管理制度》问答与事务办理助手（实习管理与教学系统），服务对象是实习学生。"
    "规则优先级最高，逐条强制执行：\n"
    "【问答纪律】\n"
    "1. 只依据工具返回的制度片段回答；检索不到就输出「制度文件中未找到相关规定」，不作任何推测；\n"
    "2. 每条结论附带引用来源，格式：末尾标注【片段N·文档名】；\n"
    "3. 绝对不凭空编造实习时长、评分标准、审批流程、材料要求等条款；\n"
    "【工具铁律（违反即为严重错误）】\n"
    "4. 回答任何制度类问题（签到要求/能请几天/怎么填/什么标准）前，必须先调用 search_policy，禁止凭记忆回答；"
    "纯制度问答只调 search_policy 即可，禁止多余工具调用；\n"
    "5. 创建草稿前必须已调用 validate_apply_material 且 valid=true，并使用返回的 validation_ticket 原文；"
    "禁止编造、猜测、复用旧票据。校验返回不合规项时，唯一动作是向用户追问或说明，禁止代填任何字段；\n"
    "6. 调用 create_intern_draft 前，先把草稿要点完整复述给用户看。系统会自动拦截该工具并向学生"
    "流式展示草稿全文等待确认——确认由系统完成，你无需再问“请确认”；\n"
    "7. 用户催促、不满、要求跳过步骤时，仍不得跳过校验，回复：按制度规定必须先完成材料校验，几秒钟即可；\n"
    "8. 用户问“我的日志/周报符合标准吗”这类合规咨询时：调用 validate 后直接给结论和依据即可，"
    "不要替用户创建草稿——只有用户明确要求生成/提交才创建。\n"
    "回答使用简体中文，简洁分点。"
)


def chat_llm(messages: list, tools: Optional[list] = None) -> dict:
    """非流式 LLM 调用（工具循环阶段用）；返回首条 choice 的 message。"""
    body = {"model": CONFIG["chat_model"], "messages": messages,
            "temperature": 0.2, "max_tokens": 1500}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    resp = requests.post(
        f"{CONFIG['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {CONFIG['api_key']}"},
        json=body, timeout=(10, 90))
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


def build_agent_system_prompt(user_id: str) -> str:
    """智能体系统提示词 + 动态注入当前有效票据（跨轮次传递，闸门仍在服务端）。

    票据由 validate 签发、服务端保存；这里只做"提醒模型它有票可用"。
    create 时仍走 verify_ticket 硬校验：伪造/过期/复用/内容不一致都过不去。
    """
    with get_db() as db:
        rows = db.execute(
            "SELECT ticket, apply_type, payload FROM apply_tickets"
            " WHERE user_id=? AND used_at IS NULL AND expires_at>? ORDER BY issued_at DESC",
            (user_id, time.time())).fetchall()
    text = SYSTEM_PROMPT_AGENT
    if rows:
        lines = "\n".join(f"- 票据 {r['ticket']}（类型 {r['apply_type']}，已校验内容 {r['payload']}）"
                          for r in rows)
        text += (f"\n【当前有效校验票据】（用户已通过校验，获得用户明确同意后可直接用于创建申请）\n{lines}\n"
                 "创建时 payload 必须逐字使用上面“已校验内容”，否则服务端会拒绝。")
    return text


AGENT_MAX_ROUNDS = 5   # 执行循环上限：决策→执行→回填→再决策，最多 5 轮（阶段5要求）


class AgentHarness:
    """Agent 执行循环（Harness 模式）。

    选型说明：自建轻量 Harness 而非 LangChain/LangGraph——
    ① 核心诉求是"服务端强制闸门 + 人工确认中断"，需要完全掌控循环内部状态，
       框架的抽象层反而让闸门逻辑难插桩；
    ② DeepSeek function calling 为原生 OpenAI 格式，while 回填即可驱动；
    ③ 零新增依赖，阶段 1~4 的检索器/规则引擎/票据闸门全部复用。

    循环骨架：模型决策 → 执行工具（结果回填消息流）→ 再决策，最多 AGENT_MAX_ROUNDS 轮。
    人工闸门：模型调用 create_intern_draft 时，循环**不执行提交**，而是
    把草稿内容流式发给前端（draft_review 事件），等待学生在卡片上点确认；
    确认动作走独立的 /api/draft/{id}/confirm 接口（服务端直接核销票据提交，
    全程不经模型）——模型无论怎么"聪明"都无法替学生按下提交键。

    用法：harness.run(question, history) 是生成器，逐段产出 SSE 帧；
    消费结束后从 .answer / .citations / .pending_draft / .failed 取结果。
    """

    # 工具执行时推给前端的状态提示
    TOOL_STATUS = {
        "search_policy": "正在检索制度…",
        "get_intern_context": "正在查询实习信息…",
        "validate_apply_material": "正在校验材料合规…",
        "create_intern_draft": "正在生成申报草稿…",
        "query_my_applies": "正在查询申请记录…",
    }

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.answer = ""          # 最终回答文本
        self.citations = None     # 最近一次 search_policy 命中（落库供历史恢复）
        self.pending_draft = None # 被人工确认中断时的草稿信息 dict
        self.failed = False       # True 表示已发出 error 帧，外层直接收尾

    # ---------- 日志：每轮决策写入 agent_rounds（阶段5分析用） ----------
    def _log_round(self, round_no, tool_name, args, t0, digest, status):
        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO agent_rounds (session_id,round_no,tool_name,args_json,"
                    "duration_ms,result_digest,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (self.session_id, round_no, tool_name,
                     json.dumps(args, ensure_ascii=False) if args is not None else None,
                     int((time.time() - t0) * 1000),
                     (digest or "")[:200], status, time.time()))
        except Exception as e:   # 日志失败不能影响主流程
            print(f"[Harness] 轮次日志写入失败：{e}")

    # ---------- 把最终回答切成小块模拟流式 ----------
    @staticmethod
    def _stream_chunks(answer: str, chunk: int = 24):
        for i in range(0, len(answer), chunk):
            yield sse("delta", {"content": answer[i:i + chunk]})

    # ---------- 主循环 ----------
    def run(self, question: str, history: list):
        """生成器：产出 SSE 帧；结果写入实例属性。"""
        llm_messages = [{"role": "system", "content": build_agent_system_prompt(self.user_id)}]
        for m in history[-HISTORY_ROUNDS * 2:]:
            llm_messages.append({"role": m["role"], "content": m["content"]})
        llm_messages.append({"role": "user", "content": question})

        for round_no in range(1, AGENT_MAX_ROUNDS + 1):
            # ===== ① 模型决策 =====
            t0 = time.time()
            try:
                msg = chat_llm(llm_messages, TOOLS)
            except requests.HTTPError as e:
                detail = ""
                try:
                    detail = e.response.json().get("error", {}).get("message", "")[:120]
                except Exception:
                    pass
                self._log_round(round_no, "llm_error", None, t0, detail or str(e), "LLM_ERROR")
                self.failed = True
                yield sse("error", {"code": "LLM_ERROR",
                                    "message": ERRORS["LLM_ERROR"][1] + f"（{detail or e}）"})
                return
            except Exception as e:
                self._log_round(round_no, "llm_error", None, t0, str(e), "LLM_ERROR")
                self.failed = True
                yield sse("error", {"code": "LLM_ERROR",
                                    "message": ERRORS["LLM_ERROR"][1] + f"（{e}）"})
                return

            tool_calls = msg.get("tool_calls")

            # ===== ②a 无工具调用 → 本轮即最终回答 =====
            if not tool_calls:
                self.answer = msg.get("content") or ""
                self._log_round(round_no, "final_answer", None, t0,
                                f"回答 {len(self.answer)} 字", "ok")
                yield sse("status", {"stage": "generating", "message": "正在生成回答…"})
                yield from self._stream_chunks(self.answer)
                return

            # ===== ②b 有工具调用 → 逐个执行并回填 =====
            llm_messages.append({"role": "assistant", "content": msg.get("content") or "",
                                 "tool_calls": tool_calls})
            # 模型在发起工具调用时附带的说明文字（如复述草稿要点），先流式放行
            pre_text = msg.get("content") or ""
            if pre_text:
                yield from self._stream_chunks(pre_text)

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield sse("status", {"stage": "tool",
                                     "message": self.TOOL_STATUS.get(name, f"正在执行 {name}…")})

                # ===== 强制中断闸门：create_intern_draft 不直接执行 =====
                if name == "create_intern_draft":
                    # 预检票据（不核销）：坏票据当场打回，模型改走重新校验
                    t1 = time.time()
                    with get_db() as db:
                        deny = verify_ticket(db, args.get("validation_ticket", ""),
                                             self.user_id, args.get("apply_type", ""),
                                             args.get("payload", {}), consume=False)
                    if deny:
                        self._log_round(round_no, name, args, t0, deny, deny)
                        llm_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                             "content": json.dumps(
                                                 {"error": deny, "message": ERRORS_TOOL_TICKET.get(deny, "票据校验失败")},
                                                 ensure_ascii=False)})
                        continue   # 回填拒绝原因，让模型自行纠正（重新校验或追问用户）
                    # 票据有效 → 草稿落库（status=pending_confirm，未核销）
                    rule = APPLY_RULES.get(args.get("apply_type", ""))
                    if not rule:
                        result = {"error": "BAD_APPLY_TYPE", "message": "不支持的申请类型"}
                        llm_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                             "content": json.dumps(result, ensure_ascii=False)})
                        continue
                    draft_id = "d_" + uuid.uuid4().hex[:10]
                    payload = args.get("payload", {})
                    with get_db() as db:
                        db.execute(
                            "INSERT INTO applies (id,session_id,user_id,apply_type,payload,status,"
                            "approval_route,ticket,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (draft_id, self.session_id, self.user_id, args["apply_type"],
                             json.dumps(payload, ensure_ascii=False), "pending_confirm",
                             rule["route"](1), args.get("validation_ticket", ""), time.time()))
                        audit_tool(db, self.session_id, name, {"apply_type": args["apply_type"]},
                                   "draft_pending")
                    self._log_round(round_no, name, args, t0,
                                    f"草稿 {draft_id} 待确认", "intercepted")
                    # 把草稿全文流式发给学生：先逐字段进 delta（打字机效果），再发卡片事件
                    review = f"已生成{rule['name']}申报草稿（单号 {draft_id}），请确认内容：\n"
                    for key, label, _ml in rule["required"]:
                        review += f"- {label}：{payload.get(key, '（空）')}\n"
                    review += f"- 审批路径：{rule['route'](1)}（依据：{rule['source']}）"
                    yield from self._stream_chunks(review)
                    self.pending_draft = {"draft_id": draft_id, "apply_type": rule["name"],
                                          "payload": payload, "approval_route": rule["route"](1),
                                          "source": rule["source"]}
                    yield sse("draft_review", self.pending_draft)
                    self.answer = review   # 落库为助手消息，刷新后草稿上下文不丢
                    return                 # 循环终止：等待学生在卡片上操作

                # ===== 普通工具：执行 → 回填 =====
                result, evs = execute_tool(name, args, self.session_id, self.user_id)
                for ev in evs:
                    yield ev
                if name == "search_policy" and isinstance(result.get("hits"), list):
                    self.citations = result["hits"]
                self._log_round(round_no, name, args, t0,
                                json.dumps(result, ensure_ascii=False),
                                result.get("error", "ok") if isinstance(result, dict) else "ok")
                llm_messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                     "content": json.dumps(result, ensure_ascii=False)})

        # ===== ③ 轮次耗尽仍无最终回答 =====
        self._log_round(AGENT_MAX_ROUNDS, "rounds_exhausted", None, time.time(),
                        "达到轮次上限", "ROUND_LIMIT")
        self.failed = True
        yield sse("error", {"code": "ROUND_LIMIT",
                            "message": f"模型未能在 {AGENT_MAX_ROUNDS} 轮内完成处理，请简化问题后重试"})


ERRORS_TOOL_TICKET = {
    "TICKET_INVALID": "校验票据无效（可能为编造）。必须先调用 validate_apply_material 获取",
    "TICKET_EXPIRED": "票据已过期，请重新调用 validate_apply_material",
    "TICKET_REUSED": "票据已被使用，请重新校验",
    "TICKET_MISMATCH": "票据与申请类型或用户不匹配",
    "PAYLOAD_MISMATCH": "草稿内容与校验时不一致（哪怕改一个字也不行），请重新校验",
}


# ---------------------------------------------------------------------------
# 错误码 → HTTPException 的统一封装
# ---------------------------------------------------------------------------

ERRORS = {
    "PARAM_MISSING":    (400, "问题内容不能为空"),
    "PARAM_TOO_LONG":   (400, f"问题长度不能超过 {MAX_QUESTION_LEN} 字"),
    "SESSION_NOT_FOUND": (404, "会话不存在，请刷新页面重试"),
    "KB_EMPTY":         (413, "知识库为空，请管理员先上传制度文档"),
    "LLM_ERROR":        (502, "模型服务暂时不可用，请稍后重试"),
    "RETRIEVAL_ERROR":  (503, "制度检索出现异常，请稍后重试"),
    "INTERNAL_ERROR":   (500, "服务内部错误，请联系管理员"),
}


def fail(code: str, extra: str = "") -> HTTPException:
    status, msg = ERRORS[code]
    return HTTPException(status_code=status, detail={"code": code, "message": msg + (f"（{extra}）" if extra else "")})


app = FastAPI(title="实习管理与教学助手")


@app.on_event("startup")
def startup():
    init_db()
    global RETRIEVER
    RETRIEVER = DBRetriever()


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    question: str


@app.get("/")
def index():
    """聊天页面。"""
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@app.get("/api/health")
def health():
    """健康检查：前端可用来在页面顶部提示知识库/模型状态。"""
    return {
        "status": "ok",
        "kb_chunks": len(RETRIEVER.chunks) if RETRIEVER else 0,
        "retrieval_mode": "hybrid" if (RETRIEVER and RETRIEVER.index is not None) else "bm25_only",
        "llm_configured": bool(CONFIG["api_key"]),
        "chat_model": CONFIG["chat_model"],
    }


@app.get("/api/sessions/{session_id}/messages")
def get_history(session_id: str):
    """恢复会话历史：返回消息数组（assistant 消息带 citations）。"""
    with get_db() as db:
        if not db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
            raise fail("SESSION_NOT_FOUND")
        rows = db.execute(
            "SELECT role, content, citations, created_at FROM messages"
            " WHERE session_id=? ORDER BY created_at", (session_id,)
        ).fetchall()
    return {"session_id": session_id, "messages": [
        {"role": r["role"], "content": r["content"],
         "citations": json.loads(r["citations"]) if r["citations"] else None}
        for r in rows]}


def sse(event: str, data: dict) -> str:
    """SSE 帧格式化。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
def chat(req: ChatRequest):
    """问答主接口：SSE 流式返回 status / sources / delta / done / error。"""
    # ---- 参数校验（先返回错误码与中文信息，SSE 未开始，可正常用 HTTP 状态码） ----
    if not req.question or not req.question.strip():
        raise fail("PARAM_MISSING")
    q = req.question.strip()
    if len(q) > MAX_QUESTION_LEN:
        raise fail("PARAM_TOO_LONG")
    if not RETRIEVER.chunks:
        raise fail("KB_EMPTY")
    # 会话校验放在流开启之前：这类错误用 HTTP 404 表达，而不是 SSE error 帧
    if req.session_id:
        with get_db() as db:
            if not db.execute("SELECT 1 FROM sessions WHERE id=?", (req.session_id,)).fetchone():
                raise fail("SESSION_NOT_FOUND")

    def generate():
        """SSE 生成器：整体 try/except，任何异常都转成 error 帧优雅收尾。"""
        session_id = req.session_id
        try:
            with get_db() as db:
                # ---- 会话：不存在则新建（存在性已在路由入口校验过） ----
                if not session_id:
                    session_id = "s_" + uuid.uuid4().hex[:12]
                    db.execute("INSERT INTO sessions (id,title,user_id,created_at,last_active_at)"
                               " VALUES (?,?,?,?,?)", (session_id, q[:20], "local", time.time(), time.time()))
                # ---- 历史上下文：最近 6 轮 ----
                history = [dict(r) for r in db.execute(
                    "SELECT role, content FROM messages WHERE session_id=? ORDER BY created_at",
                    (session_id,)).fetchall()]
                # ---- 用户消息先落库（即使后续失败，问题也不丢） ----
                db.execute("INSERT INTO messages (id,session_id,role,content,created_at)"
                           " VALUES (?,?,?,?,?)", ("m_" + uuid.uuid4().hex[:12], session_id, "user", q, time.time()))
                db.execute("UPDATE sessions SET last_active_at=? WHERE id=?", (time.time(), session_id))

            # ---- Agent Harness 执行循环：决策→执行→回填→再决策（≤5轮）----
            harness = AgentHarness(session_id, "local")
            yield from harness.run(q, history)
            if harness.failed:
                return                       # error 帧已由 Harness 发出
            answer = harness.answer
            if not answer:
                yield sse("error", {"code": "LLM_ERROR",
                                    "message": "模型未返回回答内容，请重试"})
                return

            # ---- 回答与引用落库 ----
            msg_id = "m_" + uuid.uuid4().hex[:12]
            with get_db() as db:
                db.execute("INSERT INTO messages (id,session_id,role,content,citations,created_at)"
                           " VALUES (?,?,?,?,?,?)",
                           (msg_id, session_id, "assistant", answer,
                            json.dumps(harness.citations, ensure_ascii=False) if harness.citations else None,
                            time.time()))
            yield sse("done", {"session_id": session_id, "message_id": msg_id})
        except Exception as e:   # 兜底：保证流一定有 error 帧收尾，前端不会挂死
            yield sse("error", {"code": "INTERNAL_ERROR", "message": ERRORS["INTERNAL_ERROR"][1] + f"（{e}）"})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/draft/{draft_id}/confirm")
def confirm_draft(draft_id: str):
    """学生确认草稿 → 真正提交。

    这是全系统唯一核销校验票据的消费点（人工闸门）：
    - 再次校验票据（伪造/过期/复用/内容篡改全部拒绝）并核销；
    - 服务端直接把草稿置为 submitted，全程不经模型——
      模型无论怎么引导都不可能替学生按下提交键。
    """
    with get_db() as db:
        row = db.execute("SELECT * FROM applies WHERE id=?", (draft_id,)).fetchone()
        if not row:
            raise fail("SESSION_NOT_FOUND")   # 复用 404 结构：草稿不存在
        if row["user_id"] != "local":
            raise fail("INTERNAL_ERROR")
        if row["status"] != "pending_confirm":
            return {"ok": False, "code": "ALREADY_HANDLED",
                    "message": "该草稿已处理过（已提交或已取消）"}
        payload = json.loads(row["payload"])
        deny = verify_ticket(db, row["ticket"], row["user_id"], row["apply_type"],
                             payload, consume=True)
        if deny:
            return {"ok": False, "code": deny, "message": ERRORS_TOOL_TICKET.get(deny, "票据校验失败")}
        rule = APPLY_RULES[row["apply_type"]]
        days = _days_between(payload.get("start_date", ""), payload.get("end_date", "")) \
            if row["apply_type"] == "leave" else None
        route = rule["route"](days if days and days > 0 else 1)
        db.execute("UPDATE applies SET status='submitted', approval_route=?, submitted_at=? WHERE id=?",
                   (route, time.time(), draft_id))
    return {"ok": True, "draft_id": draft_id, "status": "submitted",
            "approval_route": route, "source": rule["source"]}


@app.post("/api/draft/{draft_id}/cancel")
def cancel_draft(draft_id: str):
    """学生取消草稿：置为 cancelled，票据不核销（10 分钟后自然过期）。"""
    with get_db() as db:
        row = db.execute("SELECT * FROM applies WHERE id=?", (draft_id,)).fetchone()
        if not row:
            raise fail("SESSION_NOT_FOUND")
        if row["status"] != "pending_confirm":
            return {"ok": False, "code": "ALREADY_HANDLED",
                    "message": "该草稿已处理过（已提交或已取消）"}
        db.execute("UPDATE applies SET status='cancelled' WHERE id=?", (draft_id,))
    return {"ok": True, "draft_id": draft_id, "status": "cancelled"}


@app.exception_handler(HTTPException)
def http_exc_handler(request, exc: HTTPException):
    """把 HTTPException.detail 格式化成统一结构 {code, message}。"""
    from fastapi.responses import JSONResponse
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "INTERNAL_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(Exception)
def unhandled_exc_handler(request, exc: Exception):
    """兜底：未捕获异常也返回统一错误结构，不暴露堆栈。"""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={
        "code": "INTERNAL_ERROR", "message": ERRORS["INTERNAL_ERROR"][1]})


# ---------------------------------------------------------------------------
# 管理后台：管理员权限 + 服务端渲染（SaaS 风格）
# 权限模型：员工（免登录，只能问答）/ 管理员（账密登录，维护知识库 + 查看全部记录）
# ---------------------------------------------------------------------------

TEMPLATES = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
TEMPLATES.env.filters["ts"] = lambda v: time.strftime("%Y-%m-%d %H:%M", time.localtime(v)) if v else "—"
TOKEN_TTL = 12 * 3600   # 登录态 12 小时

# 「问答纪律」：管理后台同款展示，服务端已强制注入 SYSTEM_PROMPT
DISCIPLINE = [
    "没有查到对应条款，直接输出：制度文件中未找到相关规定，不作任何推测",
    "每一条结论都必须附带文档名称作为引用来源",
    "绝对不凭空编造实习时长、评分标准、审批流程、材料要求等管理条款",
]


def current_admin(request: Request) -> Optional[dict]:
    """从 Cookie 解析管理员登录态；无效/过期返回 None。"""
    token = request.cookies.get("admin_token")
    if not token:
        return None
    with get_db() as db:
        row = db.execute(
            "SELECT u.id, u.username FROM admin_tokens t JOIN users u ON u.id = t.user_id"
            " WHERE t.token=? AND t.expires>? AND u.role='admin'",
            (token, time.time())).fetchone()
    return dict(row) if row else None


def admin_page(request: Request, name: str, **ctx):
    """渲染管理页的统一入口：未登录一律 303 跳登录页（权限闸门）。"""
    user = current_admin(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return TEMPLATES.TemplateResponse(request=request, name=name,
                                      context={"user": user, "discipline": DISCIPLINE, **ctx})


def rebuild_retriever() -> None:
    """知识库变更后重建内存检索器（上传/删除后必须调用）。"""
    global RETRIEVER
    RETRIEVER = DBRetriever()


def kb_redirect(ok: str = "", err: str = "") -> RedirectResponse:
    """知识库操作后带提示跳转（中文提示需 URL 编码）。"""
    q = ("ok=" + urllib.parse.quote(ok)) if ok else ("err=" + urllib.parse.quote(err))
    return RedirectResponse(f"/admin/kb?{q}", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    if current_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return TEMPLATES.TemplateResponse(request=request, name="login.html",
                                      context={"error": error})


@app.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form("")):
    """账密登录：校验通过则发 HttpOnly Cookie（token 存库，可主动失效）。"""
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or row["password_hash"] != hash_pwd(password) or row["role"] != "admin":
            return TEMPLATES.TemplateResponse(request=request, name="login.html",
                                              context={"error": "用户名或密码错误，或无管理员权限"})
        token = secrets.token_hex(32)
        db.execute("INSERT INTO admin_tokens (token, user_id, expires) VALUES (?,?,?)",
                   (token, row["id"], time.time() + TOKEN_TTL))
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie("admin_token", token, httponly=True, max_age=TOKEN_TTL, samesite="lax")
    return resp


@app.get("/logout")
def logout(request: Request):
    """退出：删除服务端 token + 清 Cookie。"""
    token = request.cookies.get("admin_token")
    if token:
        with get_db() as db:
            db.execute("DELETE FROM admin_tokens WHERE token=?", (token,))
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("admin_token")
    return resp


@app.get("/admin")
def admin_dashboard(request: Request):
    """仪表盘：核心指标 + 最近会话 + 问答纪律展示。"""
    with get_db() as db:
        stats = {
            "sessions": db.execute("SELECT COUNT(*) n FROM sessions").fetchone()["n"],
            "messages": db.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"],
            "documents": db.execute("SELECT COUNT(*) n FROM kb_documents").fetchone()["n"],
            "chunks": db.execute("SELECT COUNT(*) n FROM kb_chunks").fetchone()["n"],
        }
        recent = [dict(r) for r in db.execute(
            "SELECT s.id, s.title, s.created_at, COUNT(m.id) AS msg_count"
            " FROM sessions s LEFT JOIN messages m ON m.session_id = s.id"
            " GROUP BY s.id ORDER BY s.last_active_at DESC LIMIT 8").fetchall()]
    retrieval_mode = "混合检索（语义+关键词）" if RETRIEVER.index is not None else "BM25 关键词检索（降级）"
    return admin_page(request, "dashboard.html", stats=stats, recent=recent,
                      retrieval_mode=retrieval_mode,
                      llm_model=f"{CONFIG['chat_model']}")


@app.get("/admin/kb")
def admin_kb(request: Request, ok: str = "", err: str = ""):
    """知识库管理：文档列表（含片段数）+ 上传 + 删除。"""
    with get_db() as db:
        docs = [dict(r) for r in db.execute(
            "SELECT d.id, d.title, d.status, d.created_at, COUNT(c.id) AS chunk_count"
            " FROM kb_documents d LEFT JOIN kb_chunks c ON c.document_id = d.id"
            " GROUP BY d.id ORDER BY d.created_at DESC").fetchall()]
    return admin_page(request, "kb.html", docs=docs, ok=ok, err=err)


@app.post("/admin/kb/upload")
async def admin_kb_upload(request: Request, file: UploadFile = File(...)):
    """上传制度文档（.md/.txt，≤2MB）：入库并重建检索器。"""
    if not current_admin(request):
        return RedirectResponse("/login", status_code=303)
    name = file.filename or ""
    if not name.lower().endswith((".md", ".markdown", ".txt")):
        return kb_redirect(err="仅支持 Markdown / TXT 文件")
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        return kb_redirect(err="文件超过 2MB 上限")
    text = data.decode("utf-8", errors="replace").strip()
    if len(text) < 50:
        return kb_redirect(err="文件内容过短，不像制度文档")
    with get_db() as db:
        if db.execute("SELECT 1 FROM kb_documents WHERE title=?", (name,)).fetchone():
            return kb_redirect(err="同名文档已存在，请先删除或改名")
        result = ingest_document(db, name, text)
    rebuild_retriever()
    mode = "含向量" if result["with_vectors"] else "BM25 降级"
    return kb_redirect(ok=f"{name} 入库成功：{result['chunks']} 片（{mode}）")


@app.post("/admin/kb/delete")
def admin_kb_delete(request: Request, doc_id: str = Form("")):
    """删除文档及其全部片段，并重建检索器。"""
    if not current_admin(request):
        return RedirectResponse("/login", status_code=303)
    with get_db() as db:
        db.execute("DELETE FROM kb_chunks WHERE document_id=?", (doc_id,))
        db.execute("DELETE FROM kb_documents WHERE id=?", (doc_id,))
    rebuild_retriever()
    return kb_redirect(ok="文档已删除")


@app.get("/admin/records")
def admin_records(request: Request):
    """问答记录：全部会话列表（管理员可见全部员工记录）。"""
    with get_db() as db:
        sessions = [dict(r) for r in db.execute(
            "SELECT s.id, s.title, s.created_at, s.last_active_at,"
            " SUM(CASE WHEN m.role='user' THEN 1 ELSE 0 END) AS q_count,"
            " COUNT(m.id) AS msg_count"
            " FROM sessions s LEFT JOIN messages m ON m.session_id = s.id"
            " GROUP BY s.id ORDER BY s.last_active_at DESC").fetchall()]
    return admin_page(request, "records.html", sessions=sessions)


@app.get("/admin/sessions/{session_id}")
def admin_session_detail(request: Request, session_id: str):
    """会话详情：完整对话记录，assistant 消息展开引用来源。"""
    with get_db() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return RedirectResponse("/admin/records", status_code=303)
        messages = []
        for m in db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY created_at",
                            (session_id,)).fetchall():
            item = dict(m)
            item["citations"] = json.loads(m["citations"]) if m["citations"] else []
            messages.append(item)
    return admin_page(request, "session_detail.html", session=dict(row), messages=messages)
