"""项目空间：把一批 Agent 归到同一项目，项目有独立消息会话与工作流。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects():
    rows = db.query_all("SELECT * FROM projects ORDER BY created_at DESC")
    for r in rows:
        try:
            r["agent_ids"] = json.loads(r.get("agent_ids") or "[]")
        except Exception:
            r["agent_ids"] = []
    return {"ok": True, "projects": rows}


@router.post("/create")
def create_project(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    project_id = db.new_id("proj")
    ts = db.now()
    db.execute(
        "INSERT INTO projects (project_id, name, description, agent_ids, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'active', ?, ?)",
        (project_id, name, body.get("description", ""),
         json.dumps(body.get("agent_ids", []), ensure_ascii=False), ts, ts),
    )
    db.audit("human", "project_create", project_id, {"name": name})
    return {"ok": True, "project_id": project_id}


@router.post("/{project_id}/update")
def update_project(project_id: str, body: dict):
    if not db.query_one("SELECT 1 FROM projects WHERE project_id=?", (project_id,)):
        raise HTTPException(status_code=404, detail="project not found")
    if "name" in body:
        db.execute("UPDATE projects SET name=? WHERE project_id=?", (body["name"], project_id))
    if "description" in body:
        db.execute("UPDATE projects SET description=? WHERE project_id=?", (body["description"], project_id))
    if "agent_ids" in body:
        db.execute("UPDATE projects SET agent_ids=? WHERE project_id=?",
                   (json.dumps(body["agent_ids"], ensure_ascii=False), project_id))
    db.execute("UPDATE projects SET updated_at=? WHERE project_id=?", (db.now(), project_id))
    db.audit("human", "project_update", project_id)
    return {"ok": True}


@router.post("/{project_id}/delete")
def delete_project(project_id: str):
    if not db.query_one("SELECT 1 FROM projects WHERE project_id=?", (project_id,)):
        raise HTTPException(status_code=404, detail="project not found")
    db.execute("DELETE FROM projects WHERE project_id=?", (project_id,))
    db.audit("human", "project_delete", project_id)
    return {"ok": True}


@router.get("/{project_id}")
def project_detail(project_id: str):
    row = db.query_one("SELECT * FROM projects WHERE project_id=?", (project_id,))
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        row["agent_ids"] = json.loads(row.get("agent_ids") or "[]")
    except Exception:
        row["agent_ids"] = []
    # 关联 Agent 详情
    agents = []
    for aid in row["agent_ids"]:
        a = db.get_agent(aid)
        if a:
            a["capabilities"] = json.loads(a.get("capabilities") or "[]")
            agents.append(a)
    # 项目独立会话（channel_type=task, task_id=project_id）
    msgs = db.query_all(
        "SELECT * FROM messages WHERE task_id=? ORDER BY id ASC LIMIT 100",
        (project_id,))
    # 项目关联工作流（前端按 project 过滤 workflows 表无此列，这里返回空，前端展示全部）
    return {"ok": True, "project": row, "agents": agents, "messages": msgs}


@router.get("/{project_id}/messages")
def project_messages(project_id: str, limit: int = 100):
    rows = db.query_all(
        "SELECT * FROM messages WHERE task_id=? ORDER BY id ASC LIMIT ?",
        (project_id, limit))
    return {"ok": True, "messages": rows}
