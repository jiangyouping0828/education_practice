# 贡献指南（Contributing）

感谢关注本项目！提交 Issue / PR 前请先阅读以下约定。

## 开发环境

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest 等（如提供）
cp .env.example .env                  # 本地填入自己的 API Key，切勿提交
```

## 分支与提交

- 分支命名：`feat/xxx`（新功能）、`fix/xxx`（缺陷）、`docs/xxx`（文档）。
- 提交信息遵循 Conventional Commits：
  - `feat: 支持换岗申请的日期合法性校验`
  - `fix: 修复票据过期后确认接口返回 500 的问题`
  - `docs: 补充 api.md 的 SSE 事件说明`

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
