# MVP 四大要件对照说明（工程架构 / Agent 框架 / 知识库 / 人工确认点）

> 对应要求：MVP 项目需具备 ①工程架构 ②Agent 框架 ③知识库 ④至少 3 处人工确认或审核点
> 代码基线：intern-assistant v1.3.0（16 个核心模块 2382 行，138 项自动化测试全部通过）
> 本文所有行号以 src/intern_assistant/ 为根，可在仓库中逐条核对

---

## 一、工程架构 ✓

**四层架构**（FastAPI 单服务）：

| 层 | 实现 | 证据位置 |
|---|---|---|
| 接入层 | 学生端 + 管理员端 22 个 HTTP 端点，SSE 流式（POST + fetch） | core/app.py（1278 行） |
| 编排层 | AgentHarness 智能体循环 + 票据硬闸门 | core/app.py L592-790 |
| 能力层 | 检索 / 规则引擎 / 提示词 / 安全 / 限流 五模块 | core/rag.py、core/rules.py、core/prompts.py、utils/security.py、core/rate_limit.py |
| 数据层 | SQLite 11 张表，启动建表 + 轻量迁移 + 种子数据 | core/app.py L55-160（SCHEMA）、L201（init_db） |

**工程规范配套**：pyproject.toml（ruff 六规则组）、pre-commit（含 detect-private-key）、Makefile、CI 三版本矩阵（Python 3.10/3.11/3.12）、Makefile 目标、11 个测试文件 138 个用例、30 条评测用例四维打分。

## 二、Agent 框架 ✓

**自研 AgentHarness**（core/app.py L592-790），非简单问答封装：

- **决策循环**：`AGENT_MAX_ROUNDS = 5`（L580），每轮"模型决策 → 工具执行 → 结果回填 → 再决策"（L647 for 循环）；无工具调用即流式输出最终回答，超 5 轮强制收敛（L760 rounds_exhausted）；
- **5 个工具**（TOOLS，L415）：search_policy（制度检索）、get_intern_context（本人档案）、validate_apply_material（规则校验+签发票据）、create_intern_draft（创建草稿，触发人工中断）、query_my_applies（本人记录）；execute_tool 统一分发（L452）；
- **轮次日志**：每轮写 agent_rounds 表（round_no / tool_name / duration_ms / status），一次问答的完整决策轨迹可回放；
- **SSE 帧协议**：status → delta → citations → draft_review（人工确认）→ done / error。

## 三、知识库 ✓

- **存储**：kb_documents + kb_chunks 双表（section 章节溯源、embedding BLOB、version 版本）；
- **检索**：DBRetriever 混合检索（BM25 + 向量余弦加权，L253/L287），返回带 rank/document/section/excerpt/score 五元组，即回答中的引用来源；
- **向量化两级降级**：LocalHashVectorizer（本地 bigram）兜底 + RemoteEmbedder（磁盘缓存）增强，失败自动降级 BM25；
- **维护入口**：管理员上传新制度 → ingest_document（L174）→ rebuild_retriever 热更新索引（L1218-1219），无需重启。

## 四、人工确认 / 审核点（4 处，满足"至少 3 处"）✓

### 确认点 ①：申请草稿 — 学生人工确认（运行时硬中断）
- AI 生成申报草稿后**循环终止**，状态置 `pending_confirm`（L517/L728），SSE 发出 `draft_review` 事件（L743）渲染确认卡片；
- 学生点"确认"走独立的 `/api/draft/{draft_id}/confirm`（L943），点"取消"走 `/api/draft/{draft_id}/cancel`（L978）；
- **AI 永远不能替学生提交**——确认动作是独立接口，服务端核销票据后才落库。

### 确认点 ②：审批链 — 企业导师 / 学校教师人工签核
- 每类申请的 `approval_route` 由制度规则生成（core/rules.py route 函数，如请假超 3 天"企业导师审批 → 学校实习指导教师审批"）；
- applies.status 状态机 `pending_confirm → submitted → approved / rejected`（L446），approved/rejected 只能由人工审批推进，系统不自动判审批结果。

### 确认点 ③：知识库 — 管理员人工审核上传
- 制度文档只能由管理员登录 `/admin/kb/upload` 人工上传（L1202），上传后重建索引；
- AI 与学生**无任何写入知识库的通道**——模型回答里能引用什么，由管理员审核决定。

### 确认点 ④：管理员访问 — 访问行为被强制审计
- 管理员每次查看学生记录（/admin/records、/admin/sessions/{id}）都强制写 admin_access_log（L1271：谁、何时、看了谁）；
- /admin 仪表盘展示审计流水——管理员的"审核权"本身也被审核，隐私可追溯。

---

## 五、现场演示路径（3 分钟）

1. **Agent + 知识库**：学生登录提问"实习期间请假最多能请几天？"→ 观察流式回答带制度条文引用；
2. **确认点 ①**：继续说"帮我申请 10 月 20 日到 22 日的请假，家里有事"→ AI 生成草稿出现确认卡片 → 点"取消"验证 AI 不能自行提交；再生成一次点"确认"→ 提交成功；
3. **确认点 ②**：管理员登录 /admin/records 查看 3 的申请单，可见审批路径"企业导师审批"（≤3 天）；
4. **确认点 ③④**：管理员在 /admin/kb 上传一份新制度 → 立即提问验证生效；再查看记录 → /admin 页面出现本次访问的审计流水。

## 六、交叉引用

- 详细设计：`07-详细项目设计方案.docx` 第 4.3/4.4 章（AgentHarness、工具层）、第 7 章核心流程时序；
- 需求依据：`06-需求定义文档.docx` FR-06~10、AC-05（一票否决：绕过人工确认提交 = 验收不通过）；
- 运行入口：`scripts/run.bat` → http://127.0.0.1:8000（学生端）/ /admin（管理端）。
