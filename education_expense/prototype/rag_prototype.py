# -*- coding: utf-8 -*-
"""
阶段 1 最小原型：实习制度问答（裸命令行版，无 Web）
====================================================
对应架构：
  本脚本覆盖了四层架构中的「智能体编排层」主干（RAG 检索 → LLM 生成）
  以及「数据模型层」的临时替身（FAISS 索引 + chunks.json 代替数据库）。

运行前置：
  1. pip install -r requirements.txt
  2. 配置环境变量（任选一家 OpenAI 兼容供应商）：
       OPENAI_API_KEY   必填
       OPENAI_BASE_URL  选填，默认 https://api.openai.com/v1（国内可换成兼容网关）
       CHAT_MODEL       选填，默认 gpt-4o-mini
       EMBED_MODEL      选填，默认 text-embedding-3-small
  3. python rag_prototype.py
     首次运行会对 示例文档 做切片+向量化并缓存到本地；
     之后再次运行直接加载缓存，不再重复调用向量化接口。

模块复用标记说明（★ = 后续阶段会原样/微调复用的核心模块）：
  ① llm_chat / llm_embed      → 服务层 services/llm_gateway.py（供应商可配置封装）
  ② chunk_text                → services/ingest_pipeline.py（入库流水线的切片步骤）
  ③ HybridRetriever           → services/retrieval.py（BM25+向量混合检索）
  ④ build_prompt              → 编排层 orchestrator.py 的提示词模板
  非核心部分（命令行交互、本地文件缓存）在 Web 化时会被 API 路由和数据库替换。
"""

import json
import os
import re
import sys

import numpy as np
import requests

# ---------------------------------------------------------------------------
# 0. 全局配置：供应商可配置的关键（★核心模块① 的一部分）
#    后续阶段：搬进 app/core/config.py，用 pydantic-settings 管理并支持热切换
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """简易 .env 加载器：读取脚本同目录的 .env 文件写入环境变量。

    已存在的环境变量优先（不覆盖），方便临时用 set 命令覆盖某个配置。
    """
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "chat_model": os.getenv("CHAT_MODEL", "gpt-4o-mini"),
    "embed_model": os.getenv("EMBED_MODEL", "text-embedding-3-small"),
    # 混合检索权重：向量语义 vs BM25 关键词（可按效果调整）
    "vector_weight": 0.6,
    "bm25_weight": 0.4,
    # 检索条数与切片大小
    "top_k": 3,
    "chunk_size": 500,   # 按需求：约 500 字切片
    # 本地缓存文件（Web 化后由 PostgreSQL + pgvector 取代）
    "doc_path": os.path.join(os.path.dirname(__file__), "实习制度示例.md"),
    "cache_dir": os.path.join(os.path.dirname(__file__), ".kb_cache"),
}

DOCTITLE = "实习管理制度"   # 拼进提示词，让 LLM 知道自己在回答什么制度

# ---------------------------------------------------------------------------
# ★核心模块① LLM 网关：所有大模型调用只走这两个函数，换供应商只改这里
#    后续阶段：原样搬入 services/llm_gateway.py，加超时重试与成本统计
# ---------------------------------------------------------------------------

def llm_embed(texts: list[str]) -> list[list[float]]:
    """向量化接口封装：把一批文本转成向量列表。

    兼容所有 OpenAI 格式的供应商（OpenAI / 智谱 / 通义兼容模式 / 本地 vLLM 等）。
    向量化供应商可与对话供应商不同（如对话用 DeepSeek、向量化用硅基流动），
    只需单独设置 EMBED_BASE_URL / EMBED_API_KEY / EMBED_MODEL 三个变量；
    不设置则复用对话供应商的地址和密钥。
    """
    base = os.getenv("EMBED_BASE_URL") or CONFIG["base_url"]
    key = os.getenv("EMBED_API_KEY") or CONFIG["api_key"]
    resp = requests.post(
        f"{base}/embeddings",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": CONFIG["embed_model"], "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    # 按 index 排序还原顺序，避免供应商乱序返回
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def llm_chat(system_prompt: str, user_prompt: str) -> str:
    """对话接口封装：输入系统提示词 + 用户问题，返回回答文本。

    后续阶段如需流式输出（SSE），在此函数加 stream 参数即可，
    调用方代码不需要变——这就是封装成独立函数的意义。
    """
    resp = requests.post(
        f"{CONFIG['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {CONFIG['api_key']}"},
        json={
            "model": CONFIG["chat_model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,   # 制度问答要稳，温度调低减少发散
        },
        timeout=120,
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # 把接口报错翻译成人话，方便排查 key / 余额 / 地址问题
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")[:200]
        except Exception:
            pass
        return f"[调用失败] {e.response.status_code}：{detail or str(e)}（请检查 OPENAI_API_KEY / OPENAI_BASE_URL / CHAT_MODEL）"
    return resp.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# ★核心模块② 文本切片：制度 markdown → 约 500 字的知识片段
#    后续阶段：搬入 services/ingest_pipeline.py，增加表格解析与重叠切片
# ---------------------------------------------------------------------------

def chunk_text(md_text: str, size: int = 500) -> list[str]:
    """把 markdown 文本切成 ~500 字的片段。

    策略：优先按 '## 标题' 边界切，保证一个片段讲一件事（检索质量的关键）；
    单段超过 size 再按段落二分。每片带上所属标题，方便引用溯源。
    """
    chunks: list[str] = []
    current_title = "总则"
    buf = ""

    def flush():
        """把缓冲区内容作为一片写入结果（带标题前缀）。"""
        nonlocal buf
        text = buf.strip()
        if text:
            chunks.append(f"【{current_title}】{text}")
        buf = ""

    for line in md_text.splitlines():
        # 命中 '## xxx' 视为章节边界：先把上一节落盘，再切换标题
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            flush()
            current_title = m.group(1).strip()
            continue
        # 跳过一级标题和空行噪音
        if line.startswith("# ") or not line.strip():
            continue
        buf += line.strip() + "\n"
        # 缓冲超过目标大小就先落一片（沿用当前标题）
        if len(buf) >= size:
            flush()
    flush()   # 收尾：把最后剩余的内容落盘
    return chunks


# ---------------------------------------------------------------------------
# ★核心模块③ 混合检索器：BM25（关键词） + 向量（语义） 双路召回后融合排序
#    后续阶段：搬入 services/retrieval.py，FAISS/缓存换成 pgvector 查询
# ---------------------------------------------------------------------------

class HybridRetriever:
    """混合检索器。

    为什么两路混合：
      - 向量检索擅长语义（"请假" ≈ "休假" ≈ "不在岗"），
        但对制度里的精确术语（如编号、专有名词）不稳定；
      - BM25 擅长精确关键词命中，但不懂同义改写。
      两者加权融合，是制度问答性价比最高的组合。
    """

    def __init__(self, chunks: list[str], vectors: np.ndarray | None = None):
        """vectors 传 None 时自动降级为 BM25 纯关键词检索（无向量供应商也能跑）。"""
        from rank_bm25 import BM25Okapi
        import jieba

        self.chunks = chunks
        # --- BM25 侧：中文需要先分词 ---
        self.bm25 = BM25Okapi([list(jieba.cut(c)) for c in chunks])
        # --- 向量侧：FAISS 内积索引（向量已归一化，内积=余弦相似度） ---
        self.index = None
        if vectors is not None:
            import faiss
            faiss.normalize_L2(vectors)
            self.index = faiss.IndexFlatIP(vectors.shape[1])
            self.index.add(vectors)

    @staticmethod
    def _minmax(scores: np.ndarray) -> np.ndarray:
        """把一组分数归一化到 0~1，两路分数才能加权相加。"""
        lo, hi = scores.min(), scores.max()
        return (scores - lo) / (hi - lo) if hi > lo else np.zeros_like(scores)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """双路召回 → 加权融合 → 返回 top_k 片段及得分（无向量时退化为 BM25 单路）。"""
        import jieba

        # 路 2：BM25 关键词召回分数（始终可用）
        bm25_scores = self.bm25.get_scores(list(jieba.cut(query)))

        if self.index is None:
            # 降级模式：只有 BM25 一路
            final = self._minmax(bm25_scores)
        else:
            import faiss
            # 路 1：向量召回全部片段的相似度分数
            q_vec = np.array([llm_embed([query])[0]], dtype="float32")
            faiss.normalize_L2(q_vec)
            vec_scores = np.zeros(len(self.chunks))
            d, i = self.index.search(q_vec, len(self.chunks))
            vec_scores[i[0]] = d[0]
            # 融合：各自 min-max 归一化后按权重相加
            final = (CONFIG["vector_weight"] * self._minmax(vec_scores)
                     + CONFIG["bm25_weight"] * self._minmax(bm25_scores))

        top = np.argsort(final)[::-1][:top_k]
        return [
            {"rank": r + 1, "chunk": self.chunks[idx], "score": float(final[idx])}
            for r, idx in enumerate(top)
        ]


# ---------------------------------------------------------------------------
# ★核心模块④ 提示词拼装：把检索片段塞进带约束的模板
#    后续阶段：搬入 orchestrator.py；「检索不到就承认」是防幻觉的硬约束
# ---------------------------------------------------------------------------

def build_prompt(question: str, hits: list[dict]) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt)。"""
    system = (
        f"你是《{DOCTITLE}》的问答助手。规则：\n"
        "1. 只根据提供的制度片段回答，禁止使用片段之外的任何知识；\n"
        "2. 回答末尾用【片段N】标注引用了哪些片段；\n"
        "3. 如果片段不足以回答，直接回复：制度中未找到相关规定，建议咨询管理员。"
    )
    ctx = "\n\n".join(f"片段{h['rank']}：{h['chunk']}" for h in hits)
    user = f"制度片段：\n{ctx}\n\n员工问题：{question}"
    return system, user


# ---------------------------------------------------------------------------
# 本地缓存：首次建索引后落盘，避免每次启动都重新向量化（省钱省时间）
# ---------------------------------------------------------------------------

def load_or_build_index() -> HybridRetriever:
    """优先加载本地缓存；没有缓存或制度文档更新过则重建。

    向量化失败（供应商没有 /embeddings 接口、key 无效等）时
    自动降级为 BM25 纯关键词检索，保证问答链路不断。
    """
    os.makedirs(CONFIG["cache_dir"], exist_ok=True)
    idx_path = os.path.join(CONFIG["cache_dir"], "index.faiss")
    meta_path = os.path.join(CONFIG["cache_dir"], "chunks.json")
    doc_mtime = os.path.getmtime(CONFIG["doc_path"])

    # 文档未变且缓存存在 → 直接反序列化加载
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        if meta["doc_mtime"] == doc_mtime:
            vectors = None
            if meta["had_vectors"] and os.path.exists(idx_path):
                import faiss
                fi = faiss.read_index(idx_path)
                vectors = fi.reconstruct_n(0, fi.ntotal)  # IndexFlatIP 支持还原原始向量
            mode = "混合检索" if vectors is not None else "BM25 降级检索"
            print(f"[缓存] 已加载 {len(meta['chunks'])} 个制度片段（{mode}），跳过建库")
            return HybridRetriever(meta["chunks"],
                                   np.array(vectors, dtype="float32") if vectors is not None else None)

    # 缓存缺失或文档更新 → 重建：切片 → 向量化 → 建 FAISS 索引
    with open(CONFIG["doc_path"], encoding="utf-8") as f:
        chunks = chunk_text(f.read(), CONFIG["chunk_size"])
    print(f"[建库] 制度文档切成 {len(chunks)} 片")

    vectors = None
    try:
        print("[建库] 正在向量化……")
        vectors = np.array(llm_embed(chunks), dtype="float32")
    except Exception as e:
        print(f"[降级] 向量化失败（{e.__class__.__name__}: {e}），"
              "改用 BM25 纯关键词检索。如需语义检索，请配一个支持 embeddings 的供应商。")

    retriever = HybridRetriever(chunks, vectors)   # 注意：内部会原地归一化 vectors
    if vectors is not None:
        import faiss
        idx = faiss.IndexFlatIP(vectors.shape[1])
        idx.add(vectors)                           # vectors 已被归一化，可直接落盘
        faiss.write_index(idx, idx_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"chunks": chunks, "doc_mtime": doc_mtime, "had_vectors": vectors is not None},
                  f, ensure_ascii=False)
    print(f"[建库] 完成（{'混合检索' if vectors is not None else 'BM25 降级检索'}），缓存于 {CONFIG['cache_dir']}")
    return retriever


# ---------------------------------------------------------------------------
# 命令行交互（非核心：Web 化时整段替换为 api/chat.py 的 SSE 路由）
# ---------------------------------------------------------------------------

def main() -> None:
    if not CONFIG["api_key"]:
        sys.exit("未配置 OPENAI_API_KEY 环境变量，无法调用向量化与对话接口。")
    if not os.path.exists(CONFIG["doc_path"]):
        sys.exit(f"找不到制度文档：{CONFIG['doc_path']}")

    retriever = load_or_build_index()
    print(f"\n=== 《{DOCTITLE}》问答原型（输入 q 退出）===")
    while True:
        try:
            q = input("\n你的问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("q", "quit", "exit"):
            break

        hits = retriever.search(q, CONFIG["top_k"])
        print("\n--- 命中的制度片段 ---")
        for h in hits:
            print(f"  片段{h['rank']}（相关度 {h['score']:.2f}）：{h['chunk'][:60]}……")

        system, user = build_prompt(q, hits)
        print("\n助手 > ", end="", flush=True)
        print(llm_chat(system, user))


if __name__ == "__main__":
    main()
