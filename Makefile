# 常用开发命令速查：make help
PY ?= python

.PHONY: help install dev-install lint format test run init-db clean

help:            ## 显示本帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$2}'

install:         ## 安装运行依赖
	$(PY) -m pip install -r requirements.txt

dev-install:     ## 安装开发依赖（lint + pytest）
	$(PY) -m pip install -r requirements.txt -e ".[dev]"

lint:            ## ruff 静态检查（CI 同款规则）
	$(PY) -m ruff check src tests examples

format:          ## ruff 自动格式化
	$(PY) -m ruff format src tests examples

test:            ## 运行全部测试（不调用真实 LLM）
	IMS_DB_PATH=$(shell $(PY) -c "import tempfile,os;print(os.path.join(tempfile.gettempdir(),'ims_make_test.db'))") $(PY) -m pytest tests/

run:             ## 启动开发服务（127.0.0.1:8000）
	$(PY) -m intern_assistant.main

init-db:         ## 初始化数据库（含种子账号与示例制度）
	$(PY) scripts/init_db.py

clean:           ## 清理缓存与临时产物
	$(PY) -c "import pathlib,shutil;[shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')];[p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
