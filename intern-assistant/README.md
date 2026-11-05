# 实习管理与教学助手（Intern Assistant）

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688)
![Tests](https://img.shields.io/badge/tests-138%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

基于 **RAG + Function Calling 智能体** 的实习管理与教学系统：学生用自然语言查询实习制度、提交请假/换岗/周报/日志申请，全程受**票据硬闸门**保护——AI 只能起草，不能替你提交。

## 为什么做这个

实习管理中，学生反复问相同制度问题、申请材料反复被打回、老师人工核对耗时。本项目用 AI 把"制度问答 + 申请办理"自动化，同时守住三条底线：

1. **不编造**：只依据制度文档原文回答，查不到就明确说"未找到相关规定"；
2. **可追溯**：每条回答附带文档来源，每次工具调用落 `agent_rounds` 日志；
3. **提交权在人**：AI 只能创建草稿，学生确认后才真正提交，且确认动作由服务端票据核销完成，模型无法代按。

## 功能总览

| 模块 | 能力 | 技术要点 |
|------|------|----------|
| 制度问答（RAG） | 上传制度文档 → 自动切片（约 500 字/片）→ 检索作答并附来源 | BM25(jieba) + FAISS 内积混合检索，无 embeddings 供应商时自动降级 BM25 |
| 智能体办申请 | 5 个工具：查制度 / 查实习信息 / 校验材料 / 创建草稿 / 查我的申请 | DeepSeek Function Calling，自建 Harness 最多 5 轮自收敛 |
| 硬闸门 | 草稿强制中断 → 学生确认 → 服务端核销提交 | 票据一次性 / 10 分钟过期 / 内容哈希绑定，伪造/篡改/重放一律拒绝 |
| 身份与隔离 | 学生学号登录，各看各的会话与申请单 | 独立 Cookie 令牌，越权访问 403；管理员查看记录留审计 |
| 管理后台 | 知识库上传/删除、问答记录、轮次轨迹、访问审计 | Jinja2 SSR，HttpOnly 会话，12 小时过期 |
| 安全防护 | 提示词注入检测、日志脱敏、LLM 配额限流 | 6 类注入特征留痕，手机号/身份证落日志前脱敏，10 次/分钟 + 100 次/天限流 |

## 系统架构

```mermaid
flowchart LR
    S[学生浏览器] -- SSE 流式 --> W[入口层 FastAPI]
    W --> H{Agent Harness\n最多5轮循环}
    H --> R[编排层 rag.py\n切片 / BM25+FAISS 检索]
    H --> RU[规则引擎 rules.py\n字段/字数/日期/工时]
    R --> K[(SQLite\nchat.db)]
    H --> T[(票据表\napply_tickets)]
    W -- 确认核销 --> T
    H -- LLM 网关 --> L[DeepSeek API]
    A[管理后台] --> W
```

三层防线设计：**提示词纪律（软）→ 工具 Schema 必填（中）→ 服务端票据闸门（硬）**。模型无论怎么被引导，都不可能绕过确认接口替学生按下提交键。

## 快速开始

### 环境要求

- Python 3.10 ~ 3.12
- 一个 OpenAI 兼容的 Chat API Key（如 DeepSeek）

### 安装

```bash
git clone <本仓库地址>
cd intern-assistant
pip install -r requirements.txt
cp .env.example .env        # 填入你的 API Key
```

> 开发者可改用 `pip install -e ".[dev]"`，额外获得 pytest / ruff 工具链。

### 启动

```bash
# 方式一：Windows（cmd / 双击）
scripts\run.bat

# 方式二：Linux / macOS / Git Bash
bash scripts/run.sh

# 方式三：手动（任何平台）
set PYTHONPATH=src        # Windows；Linux/macOS 用 export PYTHONPATH=src
python -m intern_assistant.main
```

> 注意：Windows 的 `bash` 命令会调用 WSL（需安装 WSL2），没装 WSL 请用 `scripts\run.bat`。

浏览器打开 http://127.0.0.1:8000

- 学生端：`/student/login` 学号登录后进入聊天页（SSE 流式打字机）。**每个学生只能看到自己的会话与申请单。**
- 管理后台：`/login` → `/admin`。后台只做管理与督导，**不提供问答入口**；所有会话查看写入审计日志。

### 演示账号

| 角色 | 账号 | 密码 | 说明 |
|------|------|------|------|
| 学生 | 20230101 | 123456 | 张三 · 设备点检助理 |
| 学生 | 20230102 | 123456 | 李四 · 产线工艺助理 |
| 学生 | 20230103 | 123456 | 王五 · 质检助理 |
| 管理员 | admin | 见 `docs/deployment.md` | 首次启动种子账号，正式环境必须修改 |

> 正式环境请删除演示学生或强制改密；学生账号建议由教务系统批量导入。

## 配置说明

所有配置集中在 `.env`（参考 `.env.example`）：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI 兼容 Chat API 密钥（DeepSeek 实测可用） |
| `OPENAI_BASE_URL` | 否 | API 地址，默认 DeepSeek 官方 |
| `CHAT_MODEL` | 否 | 对话模型，默认 `deepseek-chat` |
| `IMS_DB_PATH` | 否 | SQLite 数据库路径，默认 `data/runtime/chat.db` |

非机密默认参数（轮数上限、票据有效期等）见 `config/default.yaml`。

## 使用教程

### 学生端：一次完整的请假申请

在聊天页输入自然语言即可，无需记住任何表单字段：

```text
学生：我这周五想请一天病假，帮我提交申请。
助手：（调用 search_policy 查到请假条款 → 调用 validate_apply_material 校验材料）
      材料校验通过 ✅ 审批路由：企业导师审批（依据：实习制度示例.md·考勤与请假）
      我已生成请假草稿，请确认：
      ┌──────────────────────────────┐
      │ 类型：请假 11-14 至 11-14      │
      │ 事由：感冒发烧需要就医休息      │
      │ 路由：企业导师审批             │
      └──────────────────────────────┘
      （草稿卡片的"确认提交 / 取消"按钮亮起）
学生：（点击"确认提交"）
系统：申请已提交，等待企业导师审批。
```

关键点：**AI 只能生成草稿，"确认提交"按钮的核销动作在服务端完成**，模型无论被怎么引导都碰不到提交键。

### 多轮上下文

助手携带最近 6 轮历史，支持代词与相对日期：

```text
学生：请假超过3天需要走什么流程？
助手：超过 3 天需报学校实习指导教师审批【片段2·实习制度示例.md】
学生：那帮我提交一个4天的事假，从下周一开始。
助手：（自动解析"下周一"为具体日期 → 校验 → 草稿中断待确认）
```

### SSE 事件协议

前端不是轮询，而是消费一条 SSE 流。事件帧一览：

| 事件 | data 内容 | 时机 |
|------|-----------|------|
| `status` | `{"stage": "retrieving\|thinking", "message": "…"}` | 检索/生成阶段切换 |
| `sources` | `{"citations": [{"rank","document","section"}]}` | 检索完成，先给引用 |
| `delta` | `{"text": "增量文本"}` | LLM 流式输出，前端打字机渲染 |
| `draft_review` | `{"draft_id","apply_type","payload","ticket"}` | 草稿被拦截，等待确认 |
| `done` | `{"session_id", "rounds": N}` | 正常结束（含本轮工具调用数） |
| `error` | `{"code","message"}` | 流内错误（HTTP 状态码已无法修改） |

用 curl 直接体验：

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" -b cookies.txt \
  -d '{"question": "实习日志有什么格式要求？"}'
```

## 系统模块详解

| 模块 | 文件 | 职责与关键设计 |
|------|------|----------------|
| 入口层 | `src/intern_assistant/main.py` | `sys.path` 修正 + uvicorn 启动，Windows 双击 bat 亦可 |
| 服务层 | `core/app.py` | 全部路由、Agent Harness 循环、票据签发与核销、登录会话 |
| 编排层 | `core/rag.py` | 500 字切片（带重叠）、BM25(jieba)+FAISS 混合检索、LLM 网关、供应商可配置 |
| 规则引擎 | `core/rules.py` | 4 类申请的字段/字数/日期/工时校验，硬阈值常量化；**判定权在代码** |
| 提示词 | `core/prompts.py` | 问答纪律三条 + 工具铁律八条集中管理，改动必须过评审与评测回归 |
| 向量后端 | `core/vector.py` | 远程 embeddings 适配（带磁盘缓存防重复计费）+ 本地确定性哈希向量（离线/测试用） |
| 限流器 | `core/rate_limit.py` | 分钟+天双窗口滑动窗口，接口与 Redis 后端兼容 |
| 维护任务 | `core/maintenance.py` | 过期令牌/日志/票据清理，全部支持 dry-run 预览 |
| 评测引擎 | `evaluation/runner.py` | 30 条用例静态审计 + 四维打分 + Markdown 报告，评测标准可复现 |
| 数据导出 | `exporters.py` | 会话/申请单/轮次日志导出 CSV（UTF-8 BOM，Excel 直开），单会话 Markdown 纪要 |
| 命令行 | `cli.py` | init-db / eval / purge / backup / export / session 六个子命令 |

## 设计决策记录（ADR 摘要）

**ADR-1 为什么自建 Agent Harness 而不用 LangChain？**
智能体框架的循环是黑盒，而本系统的核心诉求恰恰是在循环内部插桩：第 N 轮强制中断草稿、票据预检、每轮留痕。自建 Harness 约 130 行，换来了对循环每一步的完全控制权。代价是放弃了框架的生态组件——对本系统规模是划算的。

**ADR-2 为什么"确认提交"必须走独立 HTTP 接口而不是让模型调用工具？**
若提交是模型的工具，那么"模型决定提交"与"学生决定提交"在协议层无法区分，提示词注入就能伪造确认。把核销做成独立接口后，提交权在 HTTP 层即与学生身份绑定——这是结构性防御，比任何提示词加固都可靠。

**ADR-3 为什么从 SQLite 起步而不是 PostgreSQL？**
试点规模（一个学院、单实例、读写比低）用 SQLite + WAL 足够，省去数据库运维成本。所有 DB 访问已收敛在 `get_db()` 单点，迁移 PostgreSQL + pgvector 时只改一处（Roadmap 已列）。

## 运维命令行（CLI）

```bash
PYTHONPATH=src python -m intern_assistant.cli init-db      # 初始化数据库
PYTHONPATH=src python -m intern_assistant.cli eval          # 离线评测 30 条用例
PYTHONPATH=src python -m intern_assistant.cli purge         # 清理过期数据（dry-run 预览）
PYTHONPATH=src python -m intern_assistant.cli purge --exec  # 确认后真删
PYTHONPATH=src python -m intern_assistant.cli backup        # 备份数据库（保留10份）
PYTHONPATH=src python -m intern_assistant.cli export sessions --out s.csv
PYTHONPATH=src python -m intern_assistant.cli session s_ab12cd34ef56
```

`eval` 子命令对 30 条用例做静态审计（工具名合法性、闸门顺序约束、违规类零工具）+ 离线回放打分，是每次改提示词/规则后的第一道回归；`purge` 落实"日志保留 180 天"策略且默认 dry-run，防误删。

## 测试与质量

```bash
make test          # 或 IMS_DB_PATH=/tmp/test.db pytest tests/
make lint          # ruff 静态检查（CI 同款规则）
```

71 条自动化测试，覆盖四个层面：

- **票据硬闸门对抗**（9 条）：伪造 / 篡改一字 / 重放 / 过期 / 换用户 / 换类型 / 预检不核销；
- **身份与数据隔离**（7 条）：跨学生读会话 / 续问 / 确认草稿全部 403，管理员不可代学生操作；
- **业务规则边界**（21 条）：30 天请假上限 / 周报 30 字 / 日志 50 字 / 工时 0~8 / 审批路由；
- **基础组件**（34 条）：脱敏、注入检测、相对日期解析、限流双窗口。

CI（GitHub Actions）在 Python 3.10 / 3.11 / 3.12 三个版本矩阵上执行 lint + 全量测试。评测方案与 30 条人工评测用例见 `docs/eval.md` 与 `data/eval_cases.json`。

### 评测结果（最近一轮）

| 类别 | 通过率 | 说明 |
|------|--------|------|
| 制度问答（含 3 条陷阱题） | 10/10 | 陷阱题全部如实回答"未找到相关规定"，零编造 |
| 工具调用 | 10/10 | 工具序列与期望一致；40 天超限在校验阶段被拒且未建草稿 |
| 违规意图 | 5/5 | 全部拒绝协助并转为合规指引，未触发任何工具 |
| 多轮上下文 | 5/5 | "从下周一开始"解析正确；缺字段时主动追问而非代填 |

详细评分标准与复现方法见 `docs/eval.md`；离线回归可随时执行
`python -m intern_assistant.cli eval`。

## 目录结构

```
├── README.md            # 本文件
├── LICENSE              # MIT 许可证
├── CHANGELOG.md         # 版本记录
├── CONTRIBUTING.md      # 贡献指南（含 Conventional Commits 规范）
├── pyproject.toml       # 项目元数据 + ruff/pytest 工具链配置
├── requirements.txt     # Python 运行依赖
├── Makefile             # 常用命令速查（make help）
├── src/intern_assistant/
│   ├── main.py          # 程序入口
│   ├── core/
│   │   ├── app.py       # 服务层：路由 + 闸门 + Agent Harness
│   │   ├── rag.py       # 编排层：切片 / 混合检索 / LLM 网关
│   │   ├── rules.py     # 业务规则引擎：申请材料合规判定
│   │   ├── prompts.py   # 系统提示词集中管理
│   │   └── rate_limit.py# LLM 配额限流器
│   ├── templates/       # 管理后台页面（Jinja2 SSR）
│   ├── static/          # 学生端聊天页
│   └── utils/           # 脱敏 / 注入检测 / 文本工具
├── docs/                # design / api / testing / deployment / security / eval
├── tests/               # pytest（与 src 结构对应）
├── examples/            # 跑得起来的 demo
├── scripts/             # 启动 / 初始化脚本（run.bat / run.sh / init_db.py）
├── config/              # 非机密默认配置
├── data/                # 样例制度文档、30 条评测用例
└── .github/             # CI / Issue / PR 模板 / pre-commit
```

## 常见问题（FAQ）

**Q：为什么 AI 不能直接帮我提交申请？**
A：设计如此。制度上申请是学生的法律意思表示，必须本人确认。系统层面用"草稿中断 + 票据核销"保证模型永远碰不到提交按钮——这也是对提示词注入攻击的结构性防御。

**Q：查不到的问题 AI 会瞎编吗？**
A：不会。系统提示词固化"查不到拒答"纪律，回答必须附文档来源；对应 3 条陷阱评测用例（宠物托管、请假驳回三倍工资等）验证拒答行为。

**Q：检索用的向量模型在哪？**
A：DeepSeek 暂无 embeddings 接口，系统自动降级为 BM25 关键词检索；配置任一 OpenAI 兼容 embeddings 服务后自动启用混合检索，无需改代码。

**Q：多个学生同时用会串数据吗？**
A：不会。会话、申请单全部绑定登录身份，读/续问/确认他人数据一律 403；有 7 条自动化隔离测试持续守护。

**Q：Windows 下 `bash scripts/run.sh` 报 Hyper-V 错误？**
A：Windows 的 `bash` 会调用 WSL。未安装 WSL2 时请直接用 `scripts\run.bat`。

**Q：API Key 泄漏了怎么办？**
A：立即在供应商后台吊销并更换 `.env`。仓库通过 pre-commit 的 detect-private-key 钩子和 `.gitignore` 双重防护，历史提交可用 `git log -S "sk-"` 自查。

## Roadmap

- [ ] 向量检索接入（硅基流动 embeddings，已预留 `llm_embed` 接口）
- [ ] 管理后台轮次轨迹分析页（慢查询 / 高频问题统计）
- [ ] 教务系统对接（学生账号与实习档案批量同步）
- [ ] PostgreSQL + pgvector 迁移（多实例部署）
- [ ] 企业微信 / 钉钉通知（草稿待确认提醒）

## 安全须知

- `.env` 含 API Key，已被 `.gitignore` 排除，**切勿提交或分享**
- `data/runtime/` 存放运行期数据库与上传文档，同样不入库
- 三条问答纪律已固化在系统提示词：查不到拒答 / 回答必附文档名 / 不编造规则
- 安全设计详见 `docs/security.md`

## License

[MIT](LICENSE)
