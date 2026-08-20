"""工具调用：Agent 发起 -> 管理岗审批 -> 底座路由到工具节点执行。"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, HTTPException

from .. import config, db
from ..schemas import ApprovalDecision, ToolCall

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/call")
def call(body: ToolCall):
    """Agent 用 skill_id 发起调用，生成 pending 请求。"""
    if config.EMERGENCY_BLOCK:
        raise HTTPException(status_code=423, detail="emergency block is active")
    skill = db.query_one("SELECT * FROM skills WHERE skill_id=? AND status='active'", (body.skill_id,))
    if not skill:
        raise HTTPException(status_code=404, detail="skill not found or disabled")
    request_id = db.new_id("toolreq")
    db.execute(
        "INSERT INTO tool_requests (request_id, agent_id, skill_id, params, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (request_id, body.agent_id, body.skill_id,
         json.dumps(body.params, ensure_ascii=False), db.now()),
    )
    db.audit(body.agent_id, "tool_call_request", body.skill_id, {"request_id": request_id})
    return {"ok": True, "request_id": request_id, "status": "pending"}


@router.post("/approvals/decide")
def decide(body: ApprovalDecision):
    """管理岗审批。通过后底座同步转发到工具节点并回写结果。"""
    manager = db.current_manager()
    if not manager:
        raise HTTPException(status_code=409, detail="no manager online")
    if manager["agent_id"] != body.manager_id:
        raise HTTPException(status_code=403, detail="only current manager can approve")
    req = db.query_one("SELECT * FROM tool_requests WHERE request_id=?", (body.request_id,))
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    if req["status"] != "pending":
        raise HTTPException(status_code=409, detail="request already decided")
    new_status = "approved" if body.approve else "denied"
    db.execute(
        "UPDATE tool_requests SET status=?, manager_id=?, decided_at=? WHERE request_id=?",
        (new_status, body.manager_id, db.now(), body.request_id),
    )
    db.audit(body.manager_id, "tool_approval", req["skill_id"],
             {"request_id": body.request_id, "decision": new_status})

    result_payload = {"ok": True, "request_id": body.request_id, "status": new_status}
    if body.approve:
        skill = db.query_one("SELECT * FROM skills WHERE skill_id=?", (req["skill_id"],))
        if not skill or not skill["endpoint_url"]:
            db.execute("UPDATE tool_requests SET status='failed', result=? WHERE request_id=?",
                       ("skill endpoint missing", body.request_id))
            return {"ok": True, "request_id": body.request_id, "status": "failed"}
        db.execute("UPDATE tool_requests SET status='executing', executed_at=? WHERE request_id=?",
                   (db.now(), body.request_id))
        try:
            with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
                resp = client.post(
                    skill["endpoint_url"],
                    json={"skill_id": skill["skill_id"],
                          "params": json.loads(req["params"] or "{}")},
                )
                resp.raise_for_status()
                result_text = resp.text
            db.execute("UPDATE tool_requests SET status='done', result=? WHERE request_id=?",
                       (result_text, body.request_id))
            db.audit("system", "tool_exec_done", req["skill_id"],
                     {"request_id": body.request_id})
            result_payload = {"ok": True, "request_id": body.request_id,
                              "status": "done", "result": result_text}
        except Exception as exc:  # noqa: BLE001
            db.execute("UPDATE tool_requests SET status='failed', result=? WHERE request_id=?",
                       (str(exc), body.request_id))
            db.audit("system", "tool_exec_failed", req["skill_id"],
                     {"request_id": body.request_id, "error": str(exc)})
            result_payload = {"ok": False, "request_id": body.request_id,
                              "status": "failed", "error": str(exc)}
    return result_payload


@router.get("/requests/pending")
def pending():
    rows = db.query_all("SELECT * FROM tool_requests WHERE status='pending' ORDER BY created_at ASC")
    return {"ok": True, "pending": rows}


@router.get("/requests/{request_id}")
def request_status(request_id: str):
    row = db.query_one("SELECT * FROM tool_requests WHERE request_id=?", (request_id,))
    if not row:
        raise HTTPException(status_code=404, detail="request not found")
    return {"ok": True, "request": row}
