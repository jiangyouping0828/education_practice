# -*- coding: utf-8 -*-
"""向量检索后端（core.vector）

提供两种向量化方案，接口一致、可配置切换：
- RemoteEmbedder：调用 OpenAI 兼容 /embeddings 接口（生产推荐，需供应商支持）；
- LocalHashVectorizer：本地确定性哈希词袋向量（零依赖、零网络，测试/降级可用）。

VectorStore 提供余弦相似度检索；DiskCache 把远程向量化结果落盘，
同一文档切片不重复计费。与 rag.py 的 BM25 形成混合检索的"向量半边"。
"""

import hashlib
import json
import math
import os
import re
from typing import Callable, Protocol

DEFAULT_DIM = 256          # 本地向量维度
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """轻量分词：英文按词、中文按单字（配合 bigram 兼顾语义连续性）。"""
    text = text or ""
    tokens = _TOKEN_RE.findall(text)
    # 中文相邻单字组成 bigram，提升短语区分度
    bigrams = [tokens[i] + tokens[i + 1]
               for i in range(len(tokens) - 1)
               if "\u4e00" <= tokens[i] <= "\u9fff" and "\u4e00" <= tokens[i + 1] <= "\u9fff"]
    return tokens + bigrams


class LocalHashVectorizer:
    """确定性哈希词袋向量化：同文本必得同向量，离线可复现（测试友好）。"""

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        self.dim = dim

    def _bucket(self, token: str) -> int:
        return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in tokenize(text):
            vec[self._bucket(tok)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class RemoteEmbedder:
    """远程 embeddings 供应商适配（OpenAI 兼容协议），带磁盘缓存。"""

    def __init__(self, embed_fn: Callable[[list[str]], list[list[float]]],
                 cache_dir: str = "", cache_prefix: str = "emb") -> None:
        self.embed_fn = embed_fn
        self.cache_dir = cache_dir
        self.cache_prefix = cache_prefix
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
        return os.path.join(self.cache_dir, f"{self.cache_prefix}_{digest}.json")

    def embed(self, text: str) -> list[float]:
        if self.cache_dir:
            path = self._cache_path(text)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        vec = self.embed_fn([text])[0]
        if self.cache_dir:
            with open(self._cache_path(text), "w", encoding="utf-8") as f:
                json.dump(vec, f)
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class VectorStore:
    """余弦相似度向量库（内存版）：add 后 search 返回 top-k 及相似度。"""

    def __init__(self) -> None:
        self._vectors: list[list[float]] = []
        self._payloads: list[dict] = []

    def __len__(self) -> int:
        return len(self._vectors)

    def add(self, vector: list[float], payload: dict) -> int:
        """入库并返回行号；要求向量维度一致。"""
        if self._vectors and len(vector) != len(self._vectors[0]):
            raise ValueError(f"向量维度不一致：期望 {len(self._vectors[0])}，收到 {len(vector)}")
        self._vectors.append(list(vector))
        self._payloads.append(payload)
        return len(self._vectors) - 1

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        num = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return num / (na * nb)

    def search(self, query_vec: list[float], top_k: int = 3) -> list[dict]:
        """返回 [{"score": float, "payload": dict}, ...]，按相似度降序。"""
        scored = [(self.cosine(query_vec, v), self._payloads[i])
                  for i, v in enumerate(self._vectors)]
        scored.sort(key=lambda x: -x[0])
        return [{"score": round(s, 6), "payload": p} for s, p in scored[:top_k]]


def build_backend(backend: str = "local", embed_fn: Callable | None = None,
                  cache_dir: str = "") -> Protocol:
    """工厂：按配置返回向量化后端。backend in {"local", "remote"}。"""
    if backend == "remote":
        if embed_fn is None:
            raise ValueError("remote 后端必须提供 embed_fn（如 rag.llm_embed）")
        return RemoteEmbedder(embed_fn, cache_dir=cache_dir)
    return LocalHashVectorizer()
