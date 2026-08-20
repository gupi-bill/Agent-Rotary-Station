"""Agent 节点注册/上下线/调岗。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from .. import db
from ..config import STATION_TOKEN
from ..schemas import AgentHeartbeat, AgentRegister, AgentUpdate, ManagerSet

router = APIRouter(prefix="/agents", tags=["agents"])


def _check_token(token: str | None) -> None:
    if STATION_TOKEN and token != STATION_TOKEN:
        raise HTTPException(status_code=401, detail="invalid station token")


@router.post("/register")
def register(body: AgentRegister, x_station_token: str | None = None):
    _check_token(x_station_token)
    if body.role not in ("worker", "toolnode"):
        raise HTTPException(status_code=400, detail="role must be worker or toolnode")
    existing = db.get_agent(body.agent_id)
    ts = db.now()
    db.execute(
        "INSERT INTO agents (agent_id, name, role, status, capabilities, endpoint_url, token, last_seen, created_at) "
        "VALUES (?, ?, ?, 'online', ?, ?, ?, ?, ?) "
        "ON CONFLICT(agent_id) DO UPDATE SET "
        "name=excluded.name, role=excluded.role, status='online', "
        "capabilities=excluded.capabilities, endpoint_url=excluded.endpoint_url, "
        "token=excluded.token, last_seen=excluded.last_seen",
        (body.agent_id, body.name, body.role, json.dumps(body.capabilities, ensure_ascii=False),
         body.endpoint_url, body.token, ts, ts),
    )
    db.audit(body.agent_id, "register", body.agent_id,
             {"role": body.role, "capabilities": body.capabilities})
    return {"ok": True, "agent_id": body.agent_id, "registered_before": existing is not None}


@router.post("/heartbeat")
def heartbeat(body: AgentHeartbeat):
    if not db.get_agent(body.agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    db.touch_agent(body.agent_id)
    return {"ok": True, "agent_id": body.agent_id, "ts": db.now()}


@router.post("/offline")
def offline(body: AgentHeartbeat):
    db.execute("UPDATE agents SET status='offline' WHERE agent_id=?", (body.agent_id,))
    db.audit(body.agent_id, "offline", body.agent_id)
    return {"ok": True}


@router.post("/{agent_id}/update")
def update(agent_id: str, body: AgentUpdate):
    if not db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    if body.name is not None:
        db.execute("UPDATE agents SET name=? WHERE agent_id=?", (body.name, agent_id))
    if body.capabilities is not None:
        db.execute("UPDATE agents SET capabilities=? WHERE agent_id=?",
                   (json.dumps(body.capabilities, ensure_ascii=False), agent_id))
    if body.endpoint_url is not None:
        db.execute("UPDATE agents SET endpoint_url=? WHERE agent_id=?",
                   (body.endpoint_url, agent_id))
    db.audit(agent_id, "update_profile", agent_id)
    return {"ok": True}


@router.get("")
def list_agents(role: str | None = None):
    if role:
        rows = db.query_all(
            "SELECT agent_id, name, role, status, capabilities, last_seen FROM agents WHERE role=?",
            (role,))
    else:
        rows = db.query_all(
            "SELECT agent_id, name, role, status, capabilities, last_seen FROM agents")
    for r in rows:
        r["capabilities"] = json.loads(r.get("capabilities") or "[]")
    return {"ok": True, "agents": rows}


@router.post("/manager/set")
def set_manager(body: ManagerSet):
    if not db.get_agent(body.agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    m = db.set_manager(body.agent_id)
    return {"ok": True, "manager": m}


@router.get("/manager/current")
def get_manager():
    m = db.current_manager()
    return {"ok": True, "manager": m}


@router.post("/manager/clear")
def clear_manager():
    """撤销管理岗：当前 manager 降回 worker。"""
    m = db.clear_manager()
    return {"ok": True, "cleared": m}
