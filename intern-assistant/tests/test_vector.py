# -*- coding: utf-8 -*-
"""vector.py 测试：确定性、相似度排序、磁盘缓存、维度校验。"""

import json
import os
import sys
import tempfile

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pytest

from intern_assistant.core.vector import (
    LocalHashVectorizer, RemoteEmbedder, VectorStore, build_backend, tokenize,
)


class TestTokenize:
    def test_english_words(self):
        assert "hello" in tokenize("hello world")

    def test_chinese_chars_and_bigrams(self):
        toks = tokenize("请假流程")
        assert "请" in toks and "请假" in toks and "假流" in toks

    def test_mixed(self):
        toks = tokenize("提交SOP文件")
        assert "SOP" in toks and "提交" in toks


class TestLocalHashVectorizer:
    def test_deterministic(self):
        v = LocalHashVectorizer()
        assert v.embed("请假超过三天") == v.embed("请假超过三天")

    def test_l2_normalized(self):
        vec = LocalHashVectorizer().embed("设备点检与保养")
        assert abs(sum(x * x for x in vec) - 1.0) < 1e-9

    def test_different_texts_differ(self):
        v = LocalHashVectorizer()
        assert v.embed("请假") != v.embed("换岗")

    def test_batch_matches_single(self):
        v = LocalHashVectorizer()
        assert v.embed_batch(["a", "b"]) == [v.embed("a"), v.embed("b")]

    def test_dim_respected(self):
        assert len(LocalHashVectorizer(dim=64).embed("x")) == 64

    def test_empty_text_safe(self):
        assert len(LocalHashVectorizer().embed("")) == 256


class TestVectorStore:
    def _store(self):
        v = LocalHashVectorizer(dim=64)
        s = VectorStore()
        s.add(v.embed("实习生请假超过三天需要学校审批"), {"doc": "考勤", "rank": 1})
        s.add(v.embed("换岗申请需要企业导师同意并备案"), {"doc": "换岗", "rank": 2})
        s.add(v.embed("周报每周五前提交"), {"doc": "周报", "rank": 3})
        return v, s

    def test_add_returns_index_and_len(self):
        v, s = self._store()
        assert len(s) == 3

    def test_search_top_k_order(self):
        v, s = self._store()
        hits = s.search(v.embed("请假三天学校审批"), top_k=2)
        assert len(hits) == 2
        assert hits[0]["payload"]["doc"] == "考勤"
        assert hits[0]["score"] >= hits[1]["score"]

    def test_search_scores_in_unit_interval(self):
        v, s = self._store()
        for h in s.search(v.embed("请假"), top_k=3):
            assert -1.0 <= h["score"] <= 1.0

    def test_dim_mismatch_rejected(self):
        s = VectorStore()
        s.add([1.0, 0.0], {})
        with pytest.raises(ValueError):
            s.add([1.0, 0.0, 0.0], {})

    def test_self_similarity_is_one(self):
        v, s = self._store()
        assert abs(s.search(v.embed("实习生请假超过三天需要学校审批"), 1)[0]["score"] - 1.0) < 1e-6


class TestRemoteEmbedder:
    def test_cache_roundtrip(self, tmp_path):
        calls = []

        def fake_embed(texts):
            calls.append(list(texts))
            return [[0.1, 0.2]]

        emb = RemoteEmbedder(fake_embed, cache_dir=str(tmp_path))
        v1 = emb.embed("同一文本")
        v2 = emb.embed("同一文本")
        assert v1 == v2 == [0.1, 0.2]
        assert len(calls) == 1          # 第二次命中缓存，不再调用远程

    def test_no_cache_dir_bypasses_disk(self):
        emb = RemoteEmbedder(lambda ts: [[1.0]], cache_dir="")
        assert emb.embed("x") == [1.0]

    def test_cache_file_is_json(self, tmp_path):
        emb = RemoteEmbedder(lambda ts: [[0.5]], cache_dir=str(tmp_path))
        emb.embed("abc")
        files = os.listdir(tmp_path)
        assert len(files) == 1 and files[0].endswith(".json")
        assert json.load(open(os.path.join(tmp_path, files[0]))) == [0.5]


class TestFactory:
    def test_local_default(self):
        assert isinstance(build_backend(), LocalHashVectorizer)

    def test_remote_requires_embed_fn(self):
        with pytest.raises(ValueError):
            build_backend("remote")
