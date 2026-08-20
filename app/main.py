"""Agent-Rotary-Station 轮转工作站入口。

底座零大模型、无内置 Agent，只做存储/注册/中转/路由/日志。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .routers import agents, memories, messages, skills, system, tasks, tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Agent-Rotary-Station",
    version="0.1.0",
    description="Agent版微信 + 多智能体调度底座（纯底座，零智能）",
    lifespan=lifespan,
)

app.include_router(agents.router)
app.include_router(tasks.router)
app.include_router(messages.router)
app.include_router(memories.router)
app.include_router(skills.router)
app.include_router(tools.router)
app.include_router(system.router)


@app.get("/")
def root():
    return {"ok": True, "station": "Agent-Rotary-Station", "version": "0.1.0",
            "docs": "/docs"}
