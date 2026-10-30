# 设计说明（Design）

> 完整方案见《实习反馈AI数智化技术落地方案v1》；本文是随代码演进的设计摘要。

## 1. 背景与目标

实习管理现状：制度传达靠群里发文件、申请靠纸质/邮件流转、教师人工审核量大、过程数据散落。目标是用 AI 数智化大部分人工环节，同时**守住"AI 不能替学生做决定"的底线**。

## 2. 总体架构（四层）

```
入口层    学生聊天页(static/index.html, SSE 打字机) / 管理后台(templates/, Jinja2 SSR)
   │
服务层    core/app.py —— FastAPI 路由、鉴权、申请规则引擎(APPLY_RULES)、
   │      票据闸门(apply_tickets + verify_ticket)、Agent Harness、审计日志
   │
编排层    core/rag.py —— 文档切片(≈500字) → 入库流水线 → BM25+FAISS 混合检索
   │      → LLM 网关(供应商可配置) → 提示词编排
   │
数据层    SQLite(data/runtime/chat.db)
          users / sessions / messages / kb_documents / kb_chunks
          / drafts / applies / apply_tickets / tool_audit_log / agent_rounds
```

## 3. 关键设计决策

### 3.1 为什么自建 Agent Harness，不用 LangChain/LangGraph

提交类操作必须**在循环内部插桩**：预检票据、强制中断、写轮次日志。自建 200 行 Harness（模型决策 → 执行工具 → 结果回填 → 再决策，上限 5 轮）换来对每一步的完全掌控，而不是在框架回调里打补丁。

### 3.2 票据硬闸门（核心安全机制）

```
validate_apply_material 校验通过
   → issue_ticket：签发 apply_tickets（user_id + apply_type + payload_hash，
     10 分钟过期，一次性）
   → Harness 预检（consume=False）→ 创建草稿 drafts(pending_confirm) → 强制中断
   → 学生点击「确认」→ POST /api/draft/{id}/confirm（唯一核销点，consume=True）
   → 服务端直接提交 → applies 落库
```

拒绝码：`TICKET_INVALID`（伪造/不存在）、`TICKET_EXPIRED`、`TICKET_REUSED`（重放）、`TICKET_MISMATCH`（换用户/换类型）、`PAYLOAD_MISMATCH`（内容被篡改，哪怕一个字）。

**确认不经模型**：LLM 无法替学生确认，架构层面杜绝"AI 擅自提交"。

### 3.3 三层防线

| 层级 | 手段 | 挡什么 |
|------|------|--------|
| 软 | 系统提示词铁律（3 条问答纪律 + 8 条工具铁律） | 绝大多数正常越界意图 |
| 中 | 工具 Schema 必填字段 + 规则引擎校验 | 参数缺失/格式错误 |
| 硬 | 服务端票据闸门 + user_id 强制过滤 | 一切绕过模型的注入与伪造 |

### 3.4 检索降级策略

DeepSeek 不提供 embeddings 接口 → 自动降级 BM25（jieba 分词）。配置硅基流动等向量化服务后自动升级为 BM25+向量混合（权重 0.4/0.6）。

## 4. 可观测性

- `agent_rounds`：每轮记录 round_no / tool_name / args_json / duration_ms / result_digest(200 字) / status(ok | intercepted | 错误码 | final_answer | ROUND_LIMIT)。
- `tool_audit_log`：工具调用审计，参数只存摘要（日志最小化）。

## 5. 已知边界与演进方向

- SQLite 适合原型与小规模试点；规模化换 PostgreSQL + pgvector。
- 管理后台暂无申请单管理页与轮次轨迹分析页。
- 语义检索需补 embeddings 供应商。
