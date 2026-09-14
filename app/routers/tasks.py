"""任务：人类下发、管理岗广播、员工组队、状态流转。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db, events, nats_bus
from ..schemas import TaskAssign, TaskBroadcast, TaskCreate, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _exists(task_id: str) -> bool:
    return db.query_one("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)) is not None


@router.post("/create")
def create(body: TaskCreate):
    task_id = db.new_id("task")
    db.execute(
        "INSERT INTO tasks (task_id, title, description, status, created_by, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pending', 'human', ?, ?)",
        (task_id, body.title, body.description, db.now(), db.now()),
    )
    db.audit("human", "task_create", task_id, {"title": body.title})
    events.publish("task_created", {"task_id": task_id, "title": body.title})
    return {"ok": True, "task_id": task_id}


@router.post("/broadcast")
def broadcast(body: TaskBroadcast):
    """管理岗确认接手并开始广播抢单。底座只记录状态，不拆分任务。"""
    if not _exists(body.task_id):
        raise HTTPException(status_code=404, detail="task not found")
    db.execute(
        "UPDATE tasks SET status='broadcasting', manager_id=?, updated_at=? WHERE task_id=?",
        (body.manager_id, db.now(), body.task_id),
    )
    db.audit(body.manager_id, "task_broadcast", body.task_id)
    nats_bus.publish_task_broadcast(body.task_id, {"task_id": body.task_id,
                                                  "manager_id": body.manager_id})
    events.publish("task_broadcast", {"task_id": body.task_id,
                                      "manager_id": body.manager_id})
    return {"ok": True, "task_id": body.task_id, "status": "broadcasting"}


@router.post("/assign")
def assign(body: TaskAssign):
    """管理岗把员工拉进任务组。"""
    if not _exists(body.task_id):
        raise HTTPException(status_code=404, detail="task not found")
    if not db.get_agent(body.agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    db.execute(
        "INSERT INTO task_members (task_id, agent_id, role, joined_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(task_id, agent_id) DO UPDATE SET role=excluded.role",
        (body.task_id, body.agent_id, body.role, db.now()),
    )
    db.audit(body.agent_id, "task_assign", body.task_id, {"role": body.role})
    return {"ok": True, "task_id": body.task_id, "agent_id": body.agent_id}


@router.post("/status")
def status(body: TaskStatus):
    if not _exists(body.task_id):
        raise HTTPException(status_code=404, detail="task not found")
    allowed = {"pending", "broadcasting", "in_progress", "done", "failed", "cancelled"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail="invalid status")
    db.execute("UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
               (body.status, db.now(), body.task_id))
    db.audit("system", "task_status", body.task_id, {"status": body.status})
    events.publish("task_status", {"task_id": body.task_id, "status": body.status})
    return {"ok": True, "task_id": body.task_id, "status": body.status}


@router.get("/{task_id}")
def detail(task_id: str):
    t = db.query_one("SELECT * FROM tasks WHERE task_id=?", (task_id,))
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    members = db.query_all("SELECT agent_id, role, joined_at FROM task_members WHERE task_id=?", (task_id,))
    return {"ok": True, "task": t, "members": members}


@router.get("")
def list_tasks(status: str | None = None):
    if status:
        rows = db.query_all("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        rows = db.query_all("SELECT * FROM tasks ORDER BY created_at DESC")
    return {"ok": True, "tasks": rows}


@router.get("/{task_id}/members")
def members(task_id: str):
    return {"ok": True, "members": db.query_all(
        "SELECT agent_id, role, joined_at FROM task_members WHERE task_id=?", (task_id,))}
