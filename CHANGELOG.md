# 更新日志（Changelog）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.3.0] - 2026-11-05

### 新增
- **向量检索后端** `core/vector.py`：远程 embeddings 适配（磁盘缓存防重复计费）+ 本地确定性哈希向量（离线/测试用）+ 余弦相似度 VectorStore，与 BM25 组成混合检索的向量半边。
- **离线评测引擎** `evaluation/runner.py`：30 条评测用例静态审计（工具名合法性/闸门顺序约束/违规类零工具）+ 四维打分（工具序列/拒答纪律/来源引用/多轮结构）+ Markdown 报告，评测标准可程序化复现。
- **运维 CLI** `cli.py`：init-db / eval / purge / backup / export / session 六个子命令；purge 默认 dry-run 防误删。
- **维护任务** `core/maintenance.py`：过期令牌/超期日志（180 天保留策略）/过期票据清理，全部支持 dry-run。
- **数据导出** `exporters.py`：会话/申请单/轮次日志导出 CSV（UTF-8 BOM，Excel 直开），单会话 Markdown 纪要；申请单导出不含 payload 正文防敏感外流。
- **运维脚本** `scripts/backup.py`（每日备份+按份保留）、`scripts/reset_admin.py`（管理员密码救援重置）。
- chat 接口接入限流：超限返回 429 `RATE_LIMITED`，不产生计费调用；提问带注入特征时留痕。

### 变更
- 业务规则引擎与提示词自 app.py 抽离为 `core/rules.py` / `core/prompts.py`（行为零变更）。
- utils 重构：脱敏与注入检测集中至 `utils/security.py`，新增文本工具 `utils/text.py`。

### 文档
- README 大幅扩充：使用教程（SSE 事件协议表/curl 示例/多轮示例）、模块详解表、设计决策记录（ADR×3）、CLI 用法、评测结果表。
- testing.md 更新至 138 条用例分布；CHANGELOG 同步。

### 测试
- 测试从 71 条扩充至 **138 条**：向量 19、评测引擎 19、维护 10、导出 9、CLI 12；全量通过。

## [1.2.0] - 2026-11-05

### 新增
- **业务规则引擎模块** `core/rules.py`：四类申请规则与硬阈值常量化（`LEAVE_MAX_DAYS=30`、工时 0~8），判定权与提示词解耦；新增 `days_between` 含首尾天数计算。
- **提示词集中管理** `core/prompts.py`：RAG 与智能体系统提示词、拒答话术常量、用户提示词拼装，便于纪律条款评审与追溯。
- **安全工具模块** `utils/security.py`：脱敏函数迁移集中 + 新增 `detect_injection` 六类提示词注入特征检测（指令覆盖/角色伪装/提示词窃取/流程绕过/材料伪造），命中留痕。
- **文本工具模块** `utils/text.py`：`cjk_len` 中英混排字数口径、`clean_text` 清洗、`parse_relative_date` 口语相对日期解析（支撑多轮上下文"从下周一开始"场景）。
- **限流器** `core/rate_limit.py`：滑动窗口双窗口（10 次/分钟、100 次/天），chat 接口超限返回 429 `RATE_LIMITED`，不产生计费调用。

### 工程化
- `pyproject.toml`：项目元数据 + ruff（E/W/F/I/B/UP）+ pytest 配置，src 布局可 `pip install -e .[dev]`。
- CI 重构：拆分 lint job（ruff check + format check），测试矩阵 Python 3.10/3.11/3.12。
- `.pre-commit-config.yaml`：detect-private-key 防密钥泄漏 + ruff 自动检查。
- `.editorconfig`、`Makefile`（make help 命令速查）。
- CONTRIBUTING：Conventional Commits 八类对照表 + 一次提交一件事的拆分原则。

### 文档
- README 重写：架构图（mermaid）、功能矩阵、配置表、FAQ、Roadmap、安全须知。
- 新增 `docs/testing.md`（测试报告：71 条用例分布与冒烟清单）、`docs/deployment.md`（部署/运维/回滚）、`docs/security.md`（威胁模型与三层防线）、`docs/eval.md`（评测方案与最新记录）。

### 测试
- 测试从 16 条扩充至 **71 条**：规则边界 21、文本工具 16、限流 6、安全 12；全量通过。

## [1.1.0] - 2026-11-05

### 修复（权限模型缺陷）
- **学生端增加登录**：`/student/login` 学号 + 密码，独立 `stu_token`（HttpOnly，12h）；未登录访问首页 303 跳转。
- **数据按学生隔离**：`sessions.user_id` 不再硬编码 `'local'`，写入当前学生 ID；会话历史读取、续问、草稿确认/取消全部校验归属，越权返回 `403 FORBIDDEN`。
- **管理员职责收敛**：移除后台导航「返回员工问答」入口，管理员不再能以学生身份提问并落库。
- **管理员访问留痕**：新增 `admin_access_log` 表，每次查看会话记录（管理员、时间、目标会话），详情页展示该会话累计查看次数并提示"访问已记录"。
- **实习档案按人查询**：`users` 增加 `name` / `profile_json`，`get_intern_context` 按登录身份返回各自岗位、企业导师、学校教师、批次。

### 新增
- 演示学生账号 3 个（20230101/20230102/20230103，密码 123456），首次启动自动创建。
- `GET /api/me` 身份接口；`FORBIDDEN` / `UNAUTHORIZED` 错误码。
- `IMS_DB_PATH` 环境变量支持（测试使用临时库，不污染真实数据）。
- `tests/test_isolation.py` 7 条隔离用例 + `conftest.py`；测试总数 16 条。

## [1.0.0] - 2026-10-30

### 新增
- **阶段 1 · RAG 裸问答原型**：约 500 字切片 + BM25/FAISS 混合检索（DeepSeek 无 embeddings 接口时自动降级 BM25），LLM 网关供应商可配置。
- **阶段 2 · 学生问答 Web 入口**：FastAPI + SSE 流式（status/sources/delta/done/error 四事件），6 轮历史上下文，前端打字机效果。
- **阶段 3 · 管理后台**：Jinja2 SSR 登录（HttpOnly Cookie 12h 会话），知识库上传/删除、问答记录查看；固化三条问答纪律（查不到拒答 / 必附文档名 / 不编造）。
- **阶段 4 · Function Calling 智能体**：5 个工具（search_policy / get_intern_context / validate_apply_material / create_intern_draft / query_my_applies），请假/换岗/周报/日志四类申请规则引擎。
- **阶段 5 · Agent 执行循环与硬闸门**：
  - 自建 Agent Harness：最多 5 轮自收敛循环，全程写入 agent_rounds 日志表（round_no / tool_name / args / 耗时 / 结果摘要 / 状态）。
  - 票据硬闸门 apply_tickets：10 分钟单次有效、用户/类型/内容哈希四重绑定，拒绝码 TICKET_INVALID / EXPIRED / REUSED / MISMATCH / PAYLOAD_MISMATCH。
  - 强制中断确认：提交类操作创建草稿（pending_confirm）即中断，学生点击"确认"经独立 HTTP 接口核销票据后服务端提交——确认是唯一消费点。
  - 三层防线：系统提示词铁律（软）+ Schema 必填（中）+ 服务端闸门（硬）。
- 评测用例集 `data/eval_cases.json`（30 条：制度问答含陷阱题 / 工具调用 / 违规意图 / 多轮上下文）。
- 上线前检查清单（数据安全 / 并发限流 / 异常兜底 / 内容安全 / 回滚方案，25 项）。

### 说明
- 项目结构按开源规范重组（src 布局 + docs/tests/examples/scripts/config/.github）。
