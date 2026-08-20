# P2 任务提示词（Agent-Rotary-Station 网页拖拽 UI）

> 把下面整段直接发给负责 P2 的新模型即可。它是一份自包含、从零开始的执行指令。

---

## 你是谁 / 要干什么

你是 **Agent-Rotary-Station（轮转工作站）v0.2 P2** 阶段的前端实现者。这个项目的定位是：

- **「Agent 版微信 + 多智能体调度底座」**——纯底座，零大模型、无内置 Agent、不推理、不思考。
- 全部智能来自外部接入的独立 Agent 节点。底座只做：存储、注册、消息中转、路由转发、日志记录、审批门控、紧急刹车。
- v0.1 已完成：Agent 注册/上下线/调岗、私聊+群聊、三层记忆池、MCP 技能市场、安全日志。
- v0.2 P0/P1 已完成：工作流后端（DAG 执行、审批挂起）、工具离线排队、Agent 心跳超时。
- **P2（你这一期）= 网页拖拽 UI**：把上面这些能力做成「看得见、拖得动」的网页控制台，重点是**可视化拖拽工作流编辑器**。

**你的交付物**：一个能跑的网页控制台，覆盖 Agent 管理、聊天、记忆池、技能市场、工作流拖拽编辑与运行、系统面板。

---

## 硬约束（违反任何一条都算失败）

1. **零大模型、零向量、零 RAG**：前端只是调用后端 REST API 的壳，**绝不**在前端引入任何 LLM SDK、embedding、向量检索、自动总结。底座不懂业务，前端也不懂。
2. **不改后端业务逻辑**：后端 `app/` 下的逻辑、表结构、审批链路是已验收的，不要动。唯一允许的**最小后端改动**见下方「必须做的后端改动」。
3. **零构建、开箱即用**：最终成品必须 `python run.bat`（或 `uvicorn app.main:app`）启动后，浏览器直接访问就能用，**不允许**要求用户先 `npm install` / `npm run build` / 配一堆环境。
4. **纯前端 + 调用已存在 API**：所有数据来自下面「后端 API 清单」，前端不直连数据库。

---

## 第一步：从目录开始（不要上来就写代码）

1. `cd` 到项目根 `Agent-Rotary-Station/`，先 `ls` 和读以下文件，确证你理解现有契约（不要凭记忆）：
   - `README.md`（整体定位与已实现的约束）
   - `app/main.py`（入口、路由挂载、**注意：当前未挂载静态文件服务，你要补**）
   - `app/schemas.py`（所有请求/响应字段，前端发请求必须对齐）
   - `app/routers/*.py`（特别是 `workflows.py`、`memories.py`、`agents.py`、`skills.py`、`tools.py`、`system.py`）
   - 现有 `webui/index.html`（目前是空壳，你从它起步）
2. 在动手前，**先规划并写出 `webui/` 的目录结构**（见下方「推荐目录结构」），用文字或注释说明每个文件职责，确认结构合理再实现。这一步是「从目录开始」的核心要求。

---

## 必须做的后端改动（唯一允许的改动，最小且必要）

当前 `app/main.py` **没有把 `webui/` 暴露成网页**。你必须在 `main.py` 末尾、`include_router` 之后，加一段最小改动来托管静态文件：

```python
from fastapi.staticfiles import StaticFiles
import os
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "..", "webui")
if os.path.isdir(WEBUI_DIR):
    app.mount("/webui", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")
```

- 访问 `http://<host>:<port>/webui/` 应直接打开 `webui/index.html`。
- 不要改任何 router 逻辑、不要加新依赖（除非 `fastapi[all]` 已含 StaticFiles，它默认就有）。
- 如果 `main.py` 已有等效挂载，跳过，不要重复。

---

## 推荐技术选型（零构建方案）

- **纯静态单页应用（SPA）**，通过 CDN 引入：
  - `React 18` + `ReactDOM` + `Babel Standalone`（浏览器内转译 JSX，省去构建）
  - **拖拽画布用 `ReactFlow`**（CDN UMD 版本）——这是工作流编辑器的核心，原生拖拽成本太高不推荐。
  - 轻量样式用原生 CSS 或 `Tailwind CDN`。
- 所有后端调用封装在一个 `api.js`（或 `api.ts` 经 Babel 转译）里，统一 `fetch` + 错误处理。
- **备选**：若担心 Babel Standalone 性能，可接受用原生 JS + 原生 HTML5 Drag&Drop 实现拖拽（工作量大但零依赖）。二选一，优先 ReactFlow 方案。

> 理由：用户要求开箱即用、零配置。ReactFlow 经 CDN 引入即可实现专业级拖拽画布，且无 npm build 步骤。

---

## 推荐目录结构（webui/）

```
webui/
├── index.html              # SPA 入口，CDN 引入 React/ReactFlow/Babel，挂载 #root
├── src/
│   ├── api.js              # 封装所有后端 fetch 调用（按下方 API 清单）
│   ├── store.js            # 简单的全局状态（logged-in agent / 当前页）
│   ├── App.jsx             # 路由/侧边栏布局
│   ├── pages/
│   │   ├── Dashboard.jsx       # 总览：在线 Agent 数、工作流数、待审批数、紧急刹车状态
│   │   ├── Agents.jsx          # Agent 注册、上下线、能力标签、管理岗 set/clear
│   │   ├── Chat.jsx            # 私聊 + 任务群聊历史（/messages/history, /messages/task/{id}）
│   │   ├── Memories.jsx        # 三层记忆池浏览 + 写记忆（触发审批）
│   │   ├── Skills.jsx          # MCP 技能市场：注册、列表、调用（call）
│   │   ├── Workflows.jsx       # 工作流列表 + 拖拽编辑器入口
│   │   ├── WorkflowEditor.jsx  # ★核心：ReactFlow 拖拽画布
│   │   └── System.jsx          # 健康检查、审计日志、紧急刹车开关
│   └── components/
│       ├── NodePalette.jsx     # 左侧可拖出的节点类型
│       ├── NodePropertyPanel.jsx# 右侧编辑选中节点的 data
│       └── ApprovalInbox.jsx   # 待审批列表（记忆/工具/工作流挂起）
└── styles.css
```

---

## 后端 API 清单（直接对齐，前缀即路由前缀）

> 基础地址：`http://<host>:<port>`（默认端口见 `app/config.py`，开发模式无 token；生产 `ARS_STATION_TOKEN` 非空时需要在请求头带鉴权——本期先按开发模式做，鉴权留 TODO）。

**Agents** `prefix=/agents`
- `POST /agents/register`  body: `{agent_id, name, role, capabilities[], endpoint_url, token}`
- `POST /agents/heartbeat` body: `{agent_id}`
- `POST /agents/offline`   body: `{agent_id}`
- `POST /agents/{agent_id}/update` body: `{name?, capabilities?, endpoint_url?}`
- `GET  /agents`           返回所有 Agent
- `POST /agents/manager/set`  body: `{agent_id}`（设管理岗）
- `GET  /agents/manager/current`
- `POST /agents/manager/clear`

**Tasks** `prefix=/tasks`
- `POST /tasks/create` body: `{title, description}`
- `POST /tasks/broadcast` body: `{task_id, manager_id}`
- `POST /tasks/assign` body: `{task_id, agent_id, role}`
- `POST /tasks/status` body: `{task_id, status}`
- `GET  /tasks/{task_id}` / `GET /tasks` / `GET /tasks/{task_id}/members`

**Messages** `prefix=/messages`
- `POST /messages/send` body: `{from_agent, channel_type, to_agent, task_id, content}`
- `GET  /messages/history?...` / `GET /messages/task/{task_id}`

**Memories** `prefix=/memories`
- `POST /memories/write` body: `{agent_id, domain, mem_key, content}` → 生成审批单，同步等 manager（超时返回 pending）
- `POST /memories/delete` body: `{agent_id, domain, mem_key}`
- `POST /memories/approvals/decide` body: `{manager_id, request_id, approve}`
- `GET  /memories/approvals/pending`
- `GET  /memories/read?reader=&domain=&mem_key=`
- `GET  /memories/list-domains?reader=`

**Skills（MCP 市场）** `prefix=/skills`
- `POST /skills/register` body: `{skill_id, name, description, param_schema, endpoint_url, provider_node}`
- `POST /skills/{skill_id}/disable`
- `GET  /skills` / `GET /skills/{skill_id}`
- `POST /skills/call` body: `{agent_id, skill_id, params}` → 走工具审批

**Tools（工具调用审批+队列）** `prefix=/tools`
- `POST /tools/call`（同 skills/call 路径别名，确认用哪个）
- `POST /tools/approvals/decide` body: `{manager_id, request_id, approve}`
- `GET  /tools/queue/pending` / `GET /tools/requests/pending` / `GET /tools/requests/{request_id}`
- 后台线程已自动补发离线队列，前端只需展示 pending 与历史。

**System** `prefix=/system`
- `GET  /system/health` / `GET /system/audit-logs`
- `GET  /system/emergency-block` / `POST /system/emergency-block/toggle`（底座最高紧急刹车）
- 注：`/system/heartbeat-check` 与 `/system/tool-queue/process` 已由 `main.py` 后台线程自动跑，**不要**在前端轮询它们（除非做手动触发按钮）。

**Workflows（P2 核心）** `prefix=/workflows`
- `POST /workflows/create` body: `{name, description, definition}`
- `GET  /workflows` / `GET /workflows/{workflow_id}`
- `POST /workflows/{workflow_id}/update` body: `{name?, description?, definition?, status?}`
- `POST /workflows/{workflow_id}/delete`
- `POST /workflows/{workflow_id}/run?trigger_by=human` → 返回 `{run_id, status, ...}`
- `GET  /workflows/runs/{run_id}` / `GET /workflows/{workflow_id}/runs`
- `POST /workflows/runs/{run_id}/approve?manager_id=human` → 恢复挂起的工作流
- `POST /workflows/runs/{run_id}/deny?manager_id=human`

### 工作流 definition 契约（拖拽编辑器必须产出的 JSON）

```json
{
  "nodes": [
    {"id": "n1", "type": "agent",       "data": {"agent_id": "a2", "content": "去干活", "to_agent": "a3"}},
    {"id": "n2", "type": "tool",        "data": {"skill_id": "echo", "params": {}, "owner_agent_id": "a2"}},
    {"id": "n3", "type": "memory_write","data": {"owner_agent_id": "a2", "domain": "agent:a2", "mem_key": "k", "content": "v"}},
    {"id": "n4", "type": "memory_read", "data": {"owner_agent_id": "a2", "domain": "global", "mem_key": ""}},
    {"id": "n5", "type": "approval",    "data": {}}
  ],
  "edges": [
    {"source": "n1", "target": "n2"},
    {"source": "n2", "target": "n3"}
  ]
}
```

- **节点类型固定 5 种**：`agent | tool | memory_write | memory_read | approval`（与后端 `NODE_TYPES` 一致，多一个都不行）。
- **必填字段**：
  - `agent` 节点：`data.agent_id`（必填）、`content`
  - `tool` 节点：`data.skill_id`（必填）、`owner_agent_id`（强烈建议填，否则 fallback 到 trigger_by）
  - `memory_write/read`：`data.owner_agent_id`（**必填**，否则后端报 404）、`domain`（合法值 `agent:<id>` / `task:<id>` / `global`）、`mem_key`
  - `approval` 节点：`data` 可空
- **连线**即执行顺序；后端用 Kahn 拓扑排序执行，有环会 400。编辑器应做环检测提示。
- `memory_write/read` 节点**必须**在节点属性面板让用户填 `owner_agent_id`（这是前端友好性重点，否则工作流会假成功）。

---

## 实现优先级（先跑通主链路，再补细节）

1. **骨架**：`index.html` + 侧边栏布局 + `api.js` 封装 + 挂载 `/webui`。
2. **Dashboard + Agents + System**：最简单，先打通「看得到数据」。
3. **Workflows 列表 + WorkflowEditor 拖拽画布（核心）**：节点调色板拖出 → 画布放置 → 连线 → 右侧属性面板编辑 `data` → 保存（调 `/workflows/create` 或 `/update`）→ 运行（调 `/run`）→ 展示 run 状态与结果。
4. **ApprovalInbox**：记忆审批、工具审批、工作流挂起审批（`/runs/{id}/approve`）统一收件箱。
5. **Memories / Skills / Chat / Tasks** 页面补全。
6. **自检**：浏览器实测「注册 Agent → 设管理岗 → 拖一个 3 节点工作流（agent→tool→memory_write）→ 运行 → 在 ApprovalInbox 批记忆 → 看 run 变 done → 记忆落库」全链路。

---

## 验收标准（你做完自己先过一遍）

- [ ] `python run.bat` 启动后，访问 `/webui/` 打开控制台，无控制台报错。
- [ ] 不引入任何 LLM / 向量 / 构建步骤（搜一下产物里有没有 `openai`/`langchain`/`@anthropic`/`numpy`/`chromadb` 等，有就删）。
- [ ] 工作流拖拽编辑器能：拖节点、连线、编辑属性、保存、运行、查看 run、审批挂起。
- [ ] 全链路实测通过（注册→管理岗→建工作流→运行→审批→结果），与 `tests/test_demo.py` 后端逻辑一致。
- [ ] 未修改 `app/routers/` 任何业务逻辑；仅 `main.py` 加了 StaticFiles 挂载。
- [ ] 在 `README.md` 追加「P2 网页控制台」一节，说明访问地址与功能，并把「v0.2 明确不实现」里的「无 WebUI 控制台」划掉/标注已完成。

---

## 交付后

把改动提交进当前 `Agent-Rotary-Station` git 仓库（本目录已是独立 git 仓库），**不要**把 `data/*.db`、日志、`__pycache__` 提交进去（已有 `.gitignore` 挡）。提交信息示例：`feat(p2): 网页拖拽控制台 + 工作流可视化编辑器`。

不要自动推送到 GitHub——推送由用户/协作者另行决定。
