#!/usr/bin/env bash
# 本地启动脚本
set -e
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "[提示] 未找到 .env，正在从模板创建，请填入 API Key 后重新运行"
  cp .env.example .env
  exit 1
fi

export PYTHONPATH=src
python -m intern_assistant.main
