# 更新日志（Changelog）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
