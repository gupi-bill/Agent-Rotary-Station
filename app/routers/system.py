"""系统：健康检查、审计日志、紧急刹车、心跳超时、工具队列。"""
from __future__ import annotations

import json

from fastapi import APIRouter

from .. import config, db

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    return {"ok": True, "station": "Agent-Rotary-Station",
            "emergency_block": config.EMERGENCY_BLOCK}


@router.get("/audit-logs")
def audit_logs(limit: int = 100, actor: str | None = None):
    if actor:
        rows = db.query_all(
            "SELECT * FROM audit_logs WHERE actor=? ORDER BY id DESC LIMIT ?",
            (actor, limit),
        )
    else:
        rows = db.query_all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        try:
            r["detail"] = json.loads(r.get("detail") or "{}")
        except json.JSONDecodeError:
            pass
    return {"ok": True, "logs": rows}


@router.get("/emergency-block")
def get_block():
    return {"ok": True, "emergency_block": config.EMERGENCY_BLOCK}


@router.post("/emergency-block/toggle")
def toggle_block(active: bool = True):
    """人类最高紧急拦截：修改 config 模块级开关，所有路由实时生效。"""
    config.EMERGENCY_BLOCK = active
    db.audit("human", "emergency_block_toggle", str(active))
    return {"ok": True, "emergency_block": config.EMERGENCY_BLOCK}


@router.post("/heartbeat-check")
def heartbeat_check():
    """手动触发心跳超时检查：超时 Agent 置为 offline。"""
    count = db.mark_stale_agents_offline(config.AGENT_HEARTBEAT_TIMEOUT)
    return {"ok": True, "marked_offline": count}


@router.post("/tool-queue/process")
def tool_queue_process():
    """手动触发待补发工具队列。"""
    from . import tools
    return tools.queue_process()
