# 更新日志（Changelog）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
