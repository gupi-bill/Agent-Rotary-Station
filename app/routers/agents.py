"""Agent 节点注册/上下线/调岗/子 Agent 编排。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from .. import config, db, events, nats_bus
from ..config import STATION_TOKEN
from ..schemas import (
    AgentAutoReply,
    AgentHeartbeat,
    AgentRegister,
    AgentUpdate,
    DelegateRequest,
    ManagerSet,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def _check_token(token: str | None) -> None:
    if STATION_TOKEN and token != STATION_TOKEN:
        raise HTTPException(status_code=401, detail="invalid station token")


def _reply_from_template(tpl: str, from_agent: str, task: str) -> str:
    """模板占位符替换：{from} → 调用方，{task} → 任务内容。"""
    try:
        return tpl.replace("{from}", from_agent).replace("{task}", task)
    except Exception:
        return tpl


def _send_message(channel_type: str, from_agent: str, to_agent: str,
                  content: str, task_id: str = "") -> str:
    """写一条消息 + 审计 + 事件广播（复用消息流水）。"""
    if config.EMERGENCY_BLOCK:
        raise HTTPException(status_code=423, detail="emergency block is active")
    msg_id = db.new_id("msg")
    db.execute(
        "INSERT INTO messages (msg_id, channel_type, from_agent, to_agent, task_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg_id, channel_type, from_agent, to_agent, task_id, content, db.now()),
    )
    db.audit(from_agent, "message_send", to_agent or task_id,
             {"channel": channel_type, "msg_id": msg_id})
    events.publish("message", {"msg_id": msg_id, "channel": channel_type,
                               "from": from_agent, "to": to_agent,
                               "task_id": task_id, "content": content})
    if channel_type == "task" and task_id:
        nats_bus.publish_task_grab(task_id, {"msg_id": msg_id})
    elif to_agent:
        nats_bus.publish_agent_inbox(to_agent, {"msg_id": msg_id})
    return msg_id


@router.post("/register")
def register(body: AgentRegister, x_station_token: str | None = None):
    _check_token(x_station_token)
    if body.role not in ("worker", "toolnode"):
        raise HTTPException(status_code=400, detail="role must be worker or toolnode")
    existing = db.get_agent(body.agent_id)
    ts = db.now()
    db.execute(
        "INSERT INTO agents (agent_id, name, role, status, capabilities, endpoint_url, token, auto_reply, last_seen, created_at) "
        "VALUES (?, ?, ?, 'online', ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(agent_id) DO UPDATE SET "
        "name=excluded.name, role=excluded.role, status='online', "
        "capabilities=excluded.capabilities, endpoint_url=excluded.endpoint_url, "
        "token=excluded.token, auto_reply=excluded.auto_reply, last_seen=excluded.last_seen",
        (body.agent_id, body.name, body.role, json.dumps(body.capabilities, ensure_ascii=False),
         body.endpoint_url, body.token,
         json.dumps(body.auto_reply or {}, ensure_ascii=False), ts, ts),
    )
    db.audit(body.agent_id, "register", body.agent_id,
             {"role": body.role, "capabilities": body.capabilities,
              "auto_reply": bool(body.auto_reply)})
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
    if body.auto_reply is not None:
        db.execute("UPDATE agents SET auto_reply=? WHERE agent_id=?",
                   (json.dumps(body.auto_reply, ensure_ascii=False), agent_id))
    db.audit(agent_id, "update_profile", agent_id)
    return {"ok": True}


@router.get("/{agent_id}")
def get_agent_detail(agent_id: str):
    """单个 Agent 详情（含 auto_reply 配置）。"""
    row = db.get_agent(agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="agent not found")
    row["capabilities"] = json.loads(row.get("capabilities") or "[]")
    try:
        row["auto_reply"] = json.loads(row.get("auto_reply") or "{}")
    except Exception:
        row["auto_reply"] = {}
    return {"ok": True, "agent": row}


@router.post("/{agent_id}/autoreply")
def set_autoreply(agent_id: str, body: AgentAutoReply):
    """配置子 Agent 自动应答：enabled + 回复模板（{from}/{task} 占位符）。"""
    if not db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    cfg = {"enabled": bool(body.enabled), "reply_template": body.reply_template}
    db.execute("UPDATE agents SET auto_reply=? WHERE agent_id=?",
               (json.dumps(cfg, ensure_ascii=False), agent_id))
    db.audit(agent_id, "autoreply_config", agent_id, cfg)
    return {"ok": True, "agent_id": agent_id, "auto_reply": cfg}


@router.get("")
def list_agents(role: str | None = None):
    if role:
        rows = db.query_all(
            "SELECT agent_id, name, role, status, capabilities, auto_reply, last_seen FROM agents WHERE role=?",
            (role,))
    else:
        rows = db.query_all(
            "SELECT agent_id, name, role, status, capabilities, auto_reply, last_seen FROM agents")
    for r in rows:
        r["capabilities"] = json.loads(r.get("capabilities") or "[]")
        try:
            r["auto_reply"] = json.loads(r.get("auto_reply") or "{}")
        except Exception:
            r["auto_reply"] = {}
    return {"ok": True, "agents": rows}


@router.post("/delegate")
def delegate(body: DelegateRequest):
    """子 Agent 委托调用：from_agent 给 to_agent 派任务。

    目标 agent 若配置了 auto_reply.enabled，底座立即按模板生成应答并写回
    （from=目标, to=调用方），返回应答内容；未配置则消息进其收件箱，返回 pending。
    """
    if not db.get_agent(body.from_agent):
        raise HTTPException(status_code=404, detail=f"caller {body.from_agent} not found")
    target = db.get_agent(body.to_agent)
    if not target:
        raise HTTPException(status_code=404, detail=f"target {body.to_agent} not found")
    req_msg = _send_message("private", body.from_agent, body.to_agent,
                            body.task_content)
    try:
        ar = json.loads(target.get("auto_reply") or "{}")
    except Exception:
        ar = {}
    if ar.get("enabled"):
        tpl = ar.get("reply_template") or "收到，{from}。任务「{task}」已记录，处理中…"
        reply = _reply_from_template(tpl, body.from_agent, body.task_content)
        reply_msg = _send_message("private", body.to_agent, body.from_agent, reply)
        db.audit(body.from_agent, "delegate", body.to_agent,
                 {"task": body.task_content, "auto_replied": True})
        return {
            "ok": True,
            "status": "replied",
            "request_msg_id": req_msg,
            "reply_msg_id": reply_msg,
            "reply": reply,
            "replied_by": body.to_agent,
        }
    db.audit(body.from_agent, "delegate", body.to_agent,
             {"task": body.task_content, "auto_replied": False})
    return {
        "ok": True,
        "status": "pending",
        "request_msg_id": req_msg,
        "reply": None,
        "hint": f"{body.to_agent} 未开启自动应答，任务已进其收件箱（见消息页）",
    }
