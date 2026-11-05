# 部署手册（Deployment）

## 1. 部署形态

| 形态 | 适用场景 | 说明 |
|------|----------|------|
| 单机直跑 | 试点 / 演示 / 一个班级规模 | 本文主体；SQLite + 进程内限流 |
| Docker / 多实例 | 全校推广 | 需先完成 PostgreSQL + pgvector 迁移与 Redis 限流后端（Roadmap） |

## 2. 环境要求

- Python 3.10 ~ 3.12（Windows / Linux / macOS 均可）
- 至少 1 个 OpenAI 兼容 Chat API（DeepSeek 实测可用）
- 磁盘：程序 + 依赖约 200MB；运行数据随知识库与日志增长（试点规模 < 1GB）

## 3. 首次部署步骤

```bash
# 1. 获取代码
git clone <仓库地址> && cd intern-assistant

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置密钥
cp .env.example .env
#    编辑 .env，填入 OPENAI_API_KEY（供应商控制台获取）

# 4. 初始化数据库（建表 + 种子账号 + 导入示例制度）
PYTHONPATH=src python scripts/init_db.py      # Windows: set PYTHONPATH=src 后运行

# 5. 启动
scripts\run.bat        # Windows
bash scripts/run.sh    # Linux / macOS
```

## 4. 种子账号与首次安全动作

首次启动自动创建：

| 账号 | 初始密码 | 动作 |
|------|----------|------|
| admin（管理员） | `uwxyp042` | **登录后立即修改**（后台无改密页时，执行 `scripts/reset_admin.py` 或直接改 users 表的 password_hash） |
| 20230101 / 20230102 / 20230103（演示学生） | `123456` | 试点演示用；正式环境删除或由教务批量导入替换 |

> 以上为演示环境凭据。任何环境上线前都必须完成：改管理员密码 → 删演示学生 → 轮换 API Key。

## 5. 日常运维

| 事项 | 频率 | 操作 |
|------|------|------|
| 数据库备份 | 每日 | 复制 `data/runtime/chat.db`（先停服务或开启 WAL）；发布前额外备份一次 |
| 日志清理 | 每月 | `agent_rounds` / `tool_audit_log` / `admin_access_log` 保留 180 天，到期归档删除 |
| 知识库更新 | 制度变更时 | 后台 `/admin/kb` 上传新版制度文档，旧版本删除（自动重新切片） |
| API Key 轮换 | 泄漏或季度 | 更新 `.env` 后重启服务 |
| 依赖升级 | 季度 | `pip list --outdated`，升级前跑 `make test` |

## 6. 升级与回滚

```bash
# 升级
git fetch && git checkout v1.2.0     # 按tag升级
pip install -r requirements.txt      # 依赖变更时
# 重启服务；观察 /api/health 与一轮问答冒烟

# 回滚（目标：≤ 10 分钟）
git checkout <上一版本tag>
pip install -r requirements.txt
# data/runtime/chat.db 用发布前备份覆盖（schema 不兼容时执行回滚SQL后重启）
```

## 7. 健康检查

| 检查点 | 方法 | 通过标准 |
|--------|------|----------|
| 进程 | `curl /api/health` | 200，返回知识库切片数与检索模式 |
| 登录链路 | 未登录访问 `/` | 303 跳登录页 |
| LLM 链路 | 发起一次真实提问 | SSE 正常出字且附来源 |
| 闸门链路 | 走一次草稿确认 | 票据核销、状态 submitted |

## 8. 常见故障

| 现象 | 排查 |
|------|------|
| 启动即退出，日志见 `INSERT ... columns` 错误 | 旧库 schema 不兼容：备份后删除重建，或按 CHANGELOG 执行迁移 SQL |
| 问答全部报 502 | API Key 失效/欠费：供应商后台核对，更新 `.env` |
| 提问返回 429 | 触发限流（10 次/分钟），属预期保护；如频繁出现评估上调阈值 |
| Windows 双击 run.bat 闪退 | 命令行运行看报错；常见为未创建 `.env`（脚本会明确提示） |
