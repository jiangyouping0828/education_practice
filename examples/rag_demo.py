# -*- coding: utf-8 -*-
"""阶段 1 RAG 裸问答演示（命令行版，无 Web 依赖）。

运行前置：
  1. pip install -r requirements.txt
  2. cp .env.example .env 并填入 API Key
运行：
  PYTHONPATH=src python examples/rag_demo.py
"""

import sys

from intern_assistant.core.rag import CONFIG, load_or_build_index, llm_chat, build_prompt, DOCTITLE


def main() -> None:
    if not CONFIG["api_key"]:
        sys.exit("请先在 .env 中配置 OPENAI_API_KEY")
    retriever = load_or_build_index()
    print("输入问题回车问答，q 退出。")
    while True:
        q = input("\n你问> ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        hits = retriever.search(q, CONFIG["top_k"])
        system_prompt, user_prompt = build_prompt(q, hits)
        print("[回答]", llm_chat(system_prompt, user_prompt))
        print("[来源]", [h.get("source", DOCTITLE) for h in hits])


if __name__ == "__main__":
    main()
