# 接口说明（API）

Base URL：`http://127.0.0.1:8000`。除登录外均需会话 Cookie（登录后签发，HttpOnly，12 小时有效）。

## 页面路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 学生端聊天页（index.html） |
| GET/POST | `/login` | 管理后台登录 |
| GET | `/admin` | 管理后台首页 |
| GET | `/admin/kb` | 知识库管理 |
| GET | `/admin/records` | 问答记录 |
| GET | `/admin/session/{id}` | 单会话轨迹（含 agent_rounds） |

## 学生端接口

### POST /api/chat（SSE 流式）

请求体：`{"session_id": "...", "message": "..."}`

SSE 事件序列（POST + fetch ReadableStream，非 EventSource）：

| 事件 | 说明 |
|------|------|
| `status` | 阶段提示（检索中 / 思考中 / 工具执行中） |
| `sources` | 命中的制度片段与文档名 |
| `delta` | 增量文本（打字机渲染） |
| `draft_review` | 创建了待确认草稿：`{draft_id, apply_type, payload, ticket}` |
| `done` | 回答结束 |
| `error` | 业务错误（流已开始，HTTP 状态码无法再改） |

### 草稿确认（唯一核销点）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/draft/{id}/confirm` | 确认提交：核销票据 → 落 applies。重复调用返回 `ALREADY_HANDLED` |
| POST | `/api/draft/{id}/cancel` | 取消草稿 |

确认/取消请求体需带 `ticket`；票据校验失败返回对应拒绝码：

```
TICKET_INVALID / TICKET_EXPIRED / TICKET_REUSED
TICKET_MISMATCH / PAYLOAD_MISMATCH / ALREADY_HANDLED
```

## 管理端接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/kb/upload` | 上传制度文档（multipart），自动切片入库 |
| POST | `/admin/kb/delete` | 删除文档及其切片 |

## 错误约定

非流式接口出错统一返回：

```json
{"code": "KB_EMPTY", "message": "知识库为空，请管理员先上传制度文档"}
```

常见 code：`KB_EMPTY`、`TICKET_*`（见上）、`ALREADY_HANDLED`、`SESSION_NOT_FOUND`。
