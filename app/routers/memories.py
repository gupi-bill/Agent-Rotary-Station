"""三层记忆池：写入/删除必须经过在岗管理岗审批。

硬性规则：
1. scope 三种：agent:<id> 私有 / task:<id> 任务组 / global 全局
2. 写/删记忆不直接操作 memories 表：
   - 先写 memory_approvals 审批单(pending)
   - 把审批请求作为消息投递给当前 manager 节点
   - 工作站同步等待 manager 审批结果（轮询审批单，带超时）
   - approve 才真正写入/删除 memories；deny 返回拒绝；超时返回 pending
3. 查询记忆按权限过滤
4. 只存原始文本，不做摘要/向量/RAG
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException

from .. import config, db, events
from ..schemas import ApprovalDecision, MemoryDelete, MemoryWrite

router = APIRouter(prefix="/memories", tags=["memories"])

# 同步等待 manager 审批的最长轮询时间（秒）
APPROVAL_WAIT_TIMEOUT = 30.0
APPROVAL_POLL_INTERVAL = 0.2


def _valid_domain(domain: str) -> bool:
    return domain == "global" or domain.startswith("agent:") or domain.startswith("task:")


def _notify_manager(request_id: str, agent_id: str, domain: str, action: str,
                    mem_key: str, content: str) -> None:
    """把审批请求作为消息投递给当前 manager 节点。"""
    manager = db.current_manager()
    if not manager:
        return
    msg_id = db.new_id("msg")
    payload = {
        "type": "memory_approval_request",
        "request_id": request_id,
        "agent_id": agent_id,
        "domain": domain,
        "action": action,
        "mem_key": mem_key,
        "content": content,
    }
    db.execute(
        "INSERT INTO messages (msg_id, channel_type, from_agent, to_agent, task_id, content, created_at) "
        "VALUES (?, 'approval', ?, ?, '', ?, ?)",
        (msg_id, agent_id, manager["agent_id"],
         json.dumps(payload, ensure_ascii=False), db.now()),
    )


def _notify_requester(request_id: str, agent_id: str, decision: str) -> None:
    """把审批结果消息回投给发起 agent。"""
    msg_id = db.new_id("msg")
    payload = {
        "type": "memory_approval_result",
        "request_id": request_id,
        "decision": decision,
    }
    db.execute(
        "INSERT INTO messages (msg_id, channel_type, from_agent, to_agent, task_id, content, created_at) "
        "VALUES (?, 'approval', 'system', ?, '', ?, ?)",
        (msg_id, agent_id, json.dumps(payload, ensure_ascii=False), db.now()),
    )


def _approval_status(request_id: str) -> str | None:
    row = db.query_one("SELECT status FROM memory_approvals WHERE request_id=?", (request_id,))
    return row["status"] if row else None


def _wait_for_decision(request_id: str) -> str:
    """同步等待 manager 审批结果，返回 approved / denied / pending。"""
    deadline = time.time() + APPROVAL_WAIT_TIMEOUT
    while time.time() < deadline:
        status = _approval_status(request_id)
        if status in ("approved", "denied"):
            return status
        time.sleep(APPROVAL_POLL_INTERVAL)
    return "pending"


def _apply_decision(req: dict, approve: bool) -> None:
    """根据审批结果真正执行写/删 memories。"""
    if not approve:
        return
    if req["action"] == "write":
        db.execute(
            "INSERT INTO memories (domain, mem_key, content, owner_agent, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(domain, mem_key) DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at",
            (req["domain"], req["mem_key"], req["content"], req["agent_id"], db.now(), db.now()),
        )
    elif req["action"] == "delete":
        db.execute("DELETE FROM memories WHERE domain=? AND mem_key=?",
                   (req["domain"], req["mem_key"]))


@router.post("/write")
def write(body: MemoryWrite):
    """发起写记忆请求：先审批后落库，同步等待 manager 决策。"""
    if config.EMERGENCY_BLOCK:
        raise HTTPException(status_code=423, detail="emergency block is active")
    if not _valid_domain(body.domain):
        raise HTTPException(status_code=400, detail="invalid domain")
    if not db.get_agent(body.agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    manager = db.current_manager()
    if not manager:
        raise HTTPException(status_code=409, detail="no manager online")
    request_id = db.new_id("memreq")
    db.execute(
        "INSERT INTO memory_approvals (request_id, agent_id, domain, action, mem_key, content, status, created_at) "
        "VALUES (?, ?, ?, 'write', ?, ?, 'pending', ?)",
        (request_id, body.agent_id, body.domain, body.mem_key, body.content, db.now()),
    )
    _notify_manager(request_id, body.agent_id, body.domain, "write", body.mem_key, body.content)
    db.audit(body.agent_id, "memory_write_request", body.domain,
             {"request_id": request_id, "mem_key": body.mem_key})

    decision = _wait_for_decision(request_id)
    if decision == "pending":
        return {"ok": True, "request_id": request_id, "status": "pending",
                "detail": "waiting for manager approval"}
    if decision == "denied":
        return {"ok": False, "request_id": request_id, "status": "denied",
                "detail": "manager denied this memory write"}
    return {"ok": True, "request_id": request_id, "status": "approved"}


@router.post("/delete")
def delete(body: MemoryDelete):
    """发起删记忆请求：先审批后删除，同步等待 manager 决策。"""
    if config.EMERGENCY_BLOCK:
        raise HTTPException(status_code=423, detail="emergency block is active")
    if not _valid_domain(body.domain):
        raise HTTPException(status_code=400, detail="invalid domain")
    manager = db.current_manager()
    if not manager:
        raise HTTPException(status_code=409, detail="no manager online")
    request_id = db.new_id("memreq")
    db.execute(
        "INSERT INTO memory_approvals (request_id, agent_id, domain, action, mem_key, content, status, created_at) "
        "VALUES (?, ?, ?, 'delete', ?, '', 'pending', ?)",
        (request_id, body.agent_id, body.domain, body.mem_key, db.now()),
    )
    _notify_manager(request_id, body.agent_id, body.domain, "delete", body.mem_key, "")
    db.audit(body.agent_id, "memory_delete_request", body.domain,
             {"request_id": request_id, "mem_key": body.mem_key})

    decision = _wait_for_decision(request_id)
    if decision == "pending":
        return {"ok": True, "request_id": request_id, "status": "pending",
                "detail": "waiting for manager approval"}
    if decision == "denied":
        return {"ok": False, "request_id": request_id, "status": "denied",
                "detail": "manager denied this memory delete"}
    return {"ok": True, "request_id": request_id, "status": "approved"}


@router.post("/approvals/decide")
def decide(body: ApprovalDecision):
    """管理岗审批：更新审批单状态；通过后立即执行落库/删除。"""
    manager = db.current_manager()
    if not manager:
        raise HTTPException(status_code=409, detail="no manager online")
    if manager["agent_id"] != body.manager_id:
        raise HTTPException(status_code=403, detail="only current manager can approve")
    req = db.query_one("SELECT * FROM memory_approvals WHERE request_id=?", (body.request_id,))
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    if req["status"] != "pending":
        raise HTTPException(status_code=409, detail="request already decided")
    new_status = "approved" if body.approve else "denied"
    db.execute(
        "UPDATE memory_approvals SET status=?, decided_at=?, decided_by=? WHERE request_id=?",
        (new_status, db.now(), body.manager_id, body.request_id),
    )
    _apply_decision(req, body.approve)
    _notify_requester(body.request_id, req["agent_id"], new_status)
    db.audit(body.manager_id, "memory_approval", req["domain"],
             {"request_id": body.request_id, "decision": new_status})
    return {"ok": True, "request_id": body.request_id, "status": new_status}


@router.get("/approvals/pending")
def pending():
    rows = db.query_all(
        "SELECT * FROM memory_approvals WHERE status='pending' ORDER BY created_at ASC"
    )
    return {"ok": True, "pending": rows}


@router.get("/read")
def read(reader: str, domain: str, mem_key: str | None = None):
    """读记忆遵循可见性规则，无需审批。"""
    if not _valid_domain(domain):
        raise HTTPException(status_code=400, detail="invalid domain")
    if not db.can_read_memory(reader, domain):
        raise HTTPException(status_code=403, detail="no permission for this domain")
    if mem_key:
        row = db.query_one("SELECT * FROM memories WHERE domain=? AND mem_key=?", (domain, mem_key))
        return {"ok": True, "memory": row}
    rows = db.query_all("SELECT * FROM memories WHERE domain=? ORDER BY updated_at DESC", (domain,))
    return {"ok": True, "memories": rows}


@router.get("/list-domains")
def list_domains(reader: str):
    """返回该 agent 可见的所有 domain。"""
    rows = db.query_all("SELECT DISTINCT domain FROM memories")
    visible = [r["domain"] for r in rows if db.can_read_memory(reader, r["domain"])]
    return {"ok": True, "domains": visible}
