# 实习管理与教学助手（Intern Assistant）

基于 **RAG + Function Calling 智能体** 的实习管理与教学系统：学生用自然语言查询实习制度、提交请假/换岗/周报/日志申请，全程受**票据硬闸门**保护——AI 只能起草，不能替你提交。

## 项目是啥

- **制度问答（RAG）**：上传实习制度文档，自动切片入库（约 500 字/片），BM25(+可选向量) 混合检索，LLM 依据原文作答并附来源；查不到就明确说"未找到"，不编造。
- **智能体办申请（Agent）**：DeepSeek Function Calling 驱动 5 个工具（查制度 / 查实习信息 / 校验材料 / 创建草稿 / 查我的申请），最多 5 轮自收敛执行循环，全程留痕（agent_rounds 日志表）。
- **强制确认闸门**：所有提交类操作先创建**草稿**并中断，学生点击"确认"后才真正提交；票据一次性核销、10 分钟过期、内容哈希绑定——伪造/篡改/重放一律拒绝。

## 怎么装

```bash
git clone <本仓库地址>
cd intern-assistant
pip install -r requirements.txt
cp .env.example .env        # 填入你的 DeepSeek / OpenAI 兼容 API Key
```

## 怎么跑

```bash
# 方式一：模块入口（推荐）
python -m intern_assistant.main

# 方式二：脚本
bash scripts/run.sh
```

浏览器打开 http://127.0.0.1:8000

- 学生端：首页即聊天界面（SSE 流式打字机）
- 管理后台：http://127.0.0.1:8000/admin （账号在首次部署时设置，**上线前务必修改为强密码**）

## 目录结构

```
├── README.md            # 本文件
├── LICENSE              # MIT 许可证
├── .gitignore           # 密钥/数据库/缓存不入库
├── CHANGELOG.md         # 版本记录
├── CONTRIBUTING.md      # 贡献指南
├── requirements.txt     # Python 依赖
├── src/intern_assistant/
│   ├── main.py          # 程序入口
│   ├── core/app.py      # 服务层：路由 + 闸门 + Agent Harness
│   ├── core/rag.py      # 编排层：切片/检索/LLM 网关
│   ├── templates/       # 管理后台页面（Jinja2 SSR）
│   ├── static/          # 学生端聊天页
│   └── utils/           # 脱敏、摘要等小工具
├── docs/                # 设计说明 / 接口文档
├── tests/               # pytest 测试（与 src 结构对应）
├── examples/            # 跑得起来的 demo
├── scripts/             # 启动/初始化脚本
├── config/              # 非机密默认配置
├── data/                # 样例制度文档、评测用例
└── .github/             # CI / Issue / PR 模板
```

## 安全须知

- `.env` 含 API Key，已被 `.gitignore` 排除，**切勿提交或分享**
- `data/runtime/` 存放运行期数据库与上传文档，同样不入库
- 三条问答纪律已固化在系统提示词：查不到拒答 / 回答必附文档名 / 不编造规则

## License

[MIT](LICENSE)
