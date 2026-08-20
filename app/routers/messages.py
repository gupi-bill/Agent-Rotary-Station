"""Agent 通讯：私聊、任务群聊，只留通信流水不转长期记忆。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import config, db
from ..schemas import MessageSend

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/send")
def send(body: MessageSend):
    if config.EMERGENCY_BLOCK:
        raise HTTPException(status_code=423, detail="emergency block is active")
    if body.channel_type not in ("private", "group", "task"):
        raise HTTPException(status_code=400, detail="invalid channel_type")
    msg_id = db.new_id("msg")
    db.execute(
        "INSERT INTO messages (msg_id, channel_type, from_agent, to_agent, task_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg_id, body.channel_type, body.from_agent, body.to_agent, body.task_id,
         body.content, db.now()),
    )
    db.audit(body.from_agent, "message_send", body.to_agent or body.task_id,
             {"channel": body.channel_type, "msg_id": msg_id})
    return {"ok": True, "msg_id": msg_id}


@router.get("/history")
def history(channel_type: str | None = None, task_id: str | None = None,
            from_agent: str | None = None, to_agent: str | None = None,
            limit: int = 50):
    sql = "SELECT * FROM messages WHERE 1=1"
    params: list = []
    if channel_type:
        sql += " AND channel_type=?"
        params.append(channel_type)
    if task_id:
        sql += " AND task_id=?"
        params.append(task_id)
    if from_agent:
        sql += " AND from_agent=?"
        params.append(from_agent)
    if to_agent:
        sql += " AND to_agent=?"
        params.append(to_agent)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = db.query_all(sql, params)
    rows.reverse()  # 按时间正序返回
    return {"ok": True, "messages": rows}


@router.get("/task/{task_id}")
def task_channel(task_id: str, limit: int = 100):
    rows = db.query_all(
        "SELECT * FROM messages WHERE task_id=? ORDER BY id ASC LIMIT ?",
        (task_id, limit),
    )
    return {"ok": True, "messages": rows}
