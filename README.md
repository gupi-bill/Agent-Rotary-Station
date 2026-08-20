# Agent-Rotary-Station 轮转工作站

Agent 版微信 + 多智能体调度底座。

**底座零大模型、无内置 Agent、不做任何推理思考**。所有思考与决策能力全部来自外部接入的独立 Agent 节点。本项目只做：存储、注册、消息中转、路由转发、日志记录。

## 角色

| 角色 | 说明 |
|------|------|
| 人类使用者 | 下发顶层任务；设置/撤销管理岗；查看日志；拥有最高紧急拦截权限 |
| 轮转工作站（本项目） | 纯底座：存储/注册/中转/路由/日志，不理解业务内容 |
| 管理岗 Agent | 普通 Agent 打上 `manager` 标签；负责任务拆分、广播抢单、审批请求；可运行时动态调岗 |
| 普通员工 Agent | 抢任务、组队、私聊、群聊；发起工具调用与记忆读写请求 |
| 工具节点 | 无模型，注册 MCP 技能，只执行审批放行后的工具请求 |

## 核心能力

- **Agent 通讯**：注册、能力标签、上下线；一对一私聊、任务群聊；消息只留流水不自动转记忆
- **三层记忆池**：`agent:<id>` 私有 / `task:<id>` 任务组互通 / `global` 全局公开；写入、删除需管理岗审批
- **MCP-Skill 技能市场**：工具节点注册 `skill_id` + 参数 schema；Agent 只凭 `skill_id` 调用，无感工具地址
- **可轮换管理岗**：管理岗只是花名册标签；运行时动态升降岗，排队请求/任务/记忆/聊天全保留
- **安全与日志**：全链路审计日志；最高紧急拦截开关可无视审批直接阻断任意请求

## 数据流

```
人类下发任务 → 工作站转发当前管理岗 → 管理岗拆分并广播抢单
员工聊天；发起工具/记忆请求 → 在岗管理岗审批 → 工作站执行/写入 → 全链路留日志
```

## 技术栈

- Python 3.11
- FastAPI
- SQLite（标准库 sqlite3，零额外依赖）
- httpx

## 快速开始

### 1. 安装依赖

```powershell
cd Agent-Rotary-Station
python -m pip install -r requirements.txt
```

### 2. 启动（二选一）

**方式 A：双击 `run.bat`**

**方式 B：命令行**

```powershell
cd Agent-Rotary-Station
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. 打开接口文档

浏览器访问：<http://127.0.0.1:8000/docs>

### 4. 运行自检

```powershell
cd Agent-Rotary-Station
python tests\test_demo.py
```

## 目录结构

```
Agent-Rotary-Station/
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── db.py              # SQLite 存储层
│   ├── config.py          # 环境变量配置
│   ├── schemas.py         # Pydantic 模型
│   └── routers/
│       ├── agents.py      # 注册/上下线/调岗
│       ├── tasks.py       # 任务
│       ├── messages.py    # 通讯
│       ├── memories.py    # 三层记忆池
│       ├── skills.py      # 技能注册
│       ├── tools.py       # 工具调用审批
│       └── system.py      # 健康/审计/紧急刹车
├── webui/                 # v0.2 P2 网页控制台（零构建静态 SPA）
│   ├── index.html         # 控制台入口
│   ├── styles.css
│   └── src/
│       ├── App.js         # 多页面壳
│       ├── api.js         # 后端 REST API 封装
│       ├── store.js       # 极简事件总线
│       └── pages/         # 各功能页面
├── tests/
│   └── test_demo.py      # 端到端自检
├── data/                  # SQLite 数据库
├── requirements.txt
├── run.bat
└── README.md
```

## 创新点

1. 调度底座零智能：不内置 Agent、不调用大模型，决策全部来自外部智能体
2. 管理角色可运行时动态调岗替换，任务不中断
3. Agent 通讯层：私聊 + 群聊，智能体之间自由协作
4. 三级记忆域：私有 / 任务组互通 / 全局互通
5. MCP 技能注册表：工具能力全局互通，Agent 无感工具部署位置
6. 完整审计链路，底座拥有紧急刹车能力

## v0.2 网页控制台（P2）

启动后浏览器访问：<http://127.0.0.1:8000/webui/>

零构建、开箱即用：纯静态 SPA，CDN 引入 React + htm + ReactFlow，前端只调用后端 REST API，不直连数据库，不引入任何 LLM/向量/RAG。

### 功能页面

- 📊 总览：Agent 数、工作流数、待审批数、紧急刹车状态
- 🤖 Agent 管理：注册、心跳、上下线、设置/撤销管理岗
- 💬 聊天：私聊 + 任务群聊历史
- 🧠 记忆池：三层记忆域浏览 + 写记忆（走审批）
- 🛠 技能市场：注册、列表、调用
- 🔀 工作流：新建、编辑、运行、查看 run、删除
- ✏️ 工作流编辑器：ReactFlow 拖拽画布，5 种节点（agent / tool / memory_write / memory_read / approval），连线即 DAG，保存前做环检测
- 📥 审批收件箱：记忆审批 + 工具审批 + 工作流挂起审批统一处理
- 🛡 系统面板：健康检查、审计日志、紧急刹车开关

### 工作流 definition 契约

```json
{
  "nodes": [
    {"id": "n1", "type": "agent", "data": {"agent_id": "a2", "content": "去干活"}},
    {"id": "n2", "type": "tool", "data": {"skill_id": "echo", "owner_agent_id": "a2", "params": {}}},
    {"id": "n3", "type": "memory_write", "data": {"owner_agent_id": "a2", "domain": "global", "mem_key": "k", "content": "v"}}
  ],
  "edges": [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}]
}
```

注意：`memory_write/read` 节点必须填写 `owner_agent_id`，否则后端会 404。

## v0.1 不实现（已迭代部分，后续仍不实现）

- ~~无 WebUI 控制台~~ → 已完成 `webui/`，访问 `/webui/`
- 不做向量检索、RAG、记忆自动压缩总结
- 不做工具离线排队、负载均衡
- 默认 HTTP 通信；IronMesh 离线网格作为可选后续扩展
