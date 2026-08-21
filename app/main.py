"""Agent-Rotary-Station 轮转工作站入口。

底座零大模型、无内置 Agent，只做存储/注册/中转/路由/日志。
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .routers import agents, files, memories, messages, skills, system, tasks, tools, workflows


def _maintenance_loop() -> None:
    """后台维护线程：心跳超时检查 + 工具队列补发。"""
    import time
    from . import config
    while True:
        try:
            db.mark_stale_agents_offline(config.AGENT_HEARTBEAT_TIMEOUT)
        except Exception:
            pass
        try:
            tools.queue_process()
        except Exception:
            pass
        time.sleep(config.TOOL_QUEUE_RETRY_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    t = threading.Thread(target=_maintenance_loop, daemon=True)
    t.start()
    yield


app = FastAPI(
    title="Agent-Rotary-Station",
    version="0.2.0",
    description="Agent版微信 + 多智能体调度底座（纯底座，零智能）",
    lifespan=lifespan,
)

# ---- CORS：允许跨域（供 BlueDeer new_ui 等外部前端直连） ----
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(tasks.router)
app.include_router(messages.router)
app.include_router(memories.router)
app.include_router(skills.router)
app.include_router(tools.router)
app.include_router(system.router)
app.include_router(workflows.router)
app.include_router(files.router)


# ---- P2 WebUI 静态托管（唯一后端改动：不修改任何 router 业务逻辑） ----
import os
from fastapi.staticfiles import StaticFiles
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "..", "webui")
if os.path.isdir(WEBUI_DIR):
    app.mount("/webui", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")


@app.get("/")
def root():
    return {"ok": True, "station": "Agent-Rotary-Station", "version": "0.2.0",
            "docs": "/docs"}
