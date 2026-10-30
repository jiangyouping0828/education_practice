#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化运行环境：创建运行目录、校验配置、预建索引缓存。

运行：PYTHONPATH=src python scripts/init_db.py
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from intern_assistant.core.rag import CONFIG, PROJECT_ROOT, load_or_build_index  # noqa: E402


def main() -> None:
    os.makedirs(os.path.join(PROJECT_ROOT, "data", "runtime"), exist_ok=True)
    print("[ok] 运行目录就绪：data/runtime/")

    if not CONFIG["api_key"]:
        print("[!!] 未配置 OPENAI_API_KEY：请复制 .env.example 为 .env 并填写")
        sys.exit(1)
    print(f"[ok] LLM：{CONFIG['chat_model']} @ {CONFIG['base_url']}")

    if not os.path.exists(CONFIG["doc_path"]):
        print(f"[!!] 找不到制度文档：{CONFIG['doc_path']}")
        sys.exit(1)

    retriever = load_or_build_index()
    print(f"[ok] 知识库索引就绪：{len(retriever.chunks)} 个切片")


if __name__ == "__main__":
    main()
