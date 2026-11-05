# 贡献指南（Contributing）

感谢关注本项目！提交 Issue / PR 前请先阅读以下约定。

## 开发环境

```bash
pip install -r requirements.txt
pip install -e ".[dev]"               # 含 pytest / ruff / httpx 开发工具
cp .env.example .env                  # 本地填入自己的 API Key，切勿提交
pre-commit install                    # 提交前自动跑卫生检查（见 .pre-commit-config.yaml）
```

## 常用命令

| 命令 | 作用 |
|------|------|
| `make lint` | ruff 静态检查（与 CI 同规则） |
| `make format` | ruff 自动格式化 |
| `make test` | 运行全部测试（不调用真实 LLM） |
| `make run` | 本地启动开发服务 |
| `make help` | 查看全部命令 |

## 分支与提交

- 分支命名：`feat/xxx`（新功能）、`fix/xxx`（缺陷）、`docs/xxx`（文档）、`test/xxx`（补测试）。
- 提交信息遵循 Conventional Commits（type 前缀 + 中文摘要 + 空行 + 说明正文）：

  | type | 用途 | 示例 |
  |------|------|------|
  | `feat` | 新功能 | `feat: 支持换岗申请的日期合法性校验` |
  | `fix` | 缺陷修复 | `fix: 修复票据过期后确认接口返回 500 的问题` |
  | `docs` | 仅文档 | `docs: 补充 api.md 的 SSE 事件说明` |
  | `refactor` | 重构（不改行为） | `refactor: APPLY_RULES 抽离至 core/rules.py` |
  | `test` | 仅测试 | `test: 补充请假 30 天上限的边界用例` |
  | `chore` | 构建/工具链 | `chore: 添加 Makefile 常用命令速查` |
  | `ci` | 流水线 | `ci: 增加 lint job 与 Python 3.10-3.12 矩阵` |
  | `style` | 代码风格 | `style: ruff format 全量格式化` |

- **一次提交只做一件事**：功能与其测试可以同 commit，但文档、格式化、依赖变更应拆开，保证每个 commit 可独立回滚。
- 提交正文说明"为什么改"，而不是复述"改了什么"（diff 已经说明后者）。

## 提交 PR 前

1. `pytest tests/ -v` 全部通过（尤其是票据硬闸门的对抗用例，一个都不能破）。
2. 不提交 `.env`、`data/runtime/`、`*.db` 等本地数据。
3. 涉及闸门/工具逻辑的改动，请在 PR 描述中写明**对防线的影响**（软/中/硬三层是否变化）。
4. 新增接口请同步更新 `docs/api.md`；行为变更请更新 `CHANGELOG.md`。

## 安全红线（PR 审查重点）

以下改动原则上不予合并，除非有明确的安全评审结论：

- 任何绕过/弱化票据核销逻辑（apply_tickets 唯一消费点必须是确认接口）。
- 在日志或审计表中落学生姓名、手机号、身份证号等明文敏感字段。
- 修改系统提示词中的三条问答纪律而不补充对应评测用例。
