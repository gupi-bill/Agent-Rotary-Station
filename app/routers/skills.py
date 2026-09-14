"""MCP-Skill 全局技能注册表。工具节点上线注册，Agent 用 skill_id 调用。

/skill/call 复用 /tools/call 的审批链路：调用不直接执行工具，
先落 tool_requests(pending)，等 manager 在 /tools/approvals/decide 放行后才执行。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from .. import db
from ..schemas import SkillRegister, ToolCall

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("/register")
def register(body: SkillRegister):
    db.execute(
        "INSERT INTO skills (skill_id, name, description, param_schema, endpoint_url, provider_node, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'active', ?) "
        "ON CONFLICT(skill_id) DO UPDATE SET "
        "name=excluded.name, description=excluded.description, param_schema=excluded.param_schema, "
        "endpoint_url=excluded.endpoint_url, provider_node=excluded.provider_node, status='active'",
        (body.skill_id, body.name, body.description,
         json.dumps(body.param_schema, ensure_ascii=False),
         body.endpoint_url, body.provider_node, db.now()),
    )
    db.audit(body.provider_node or "toolnode", "skill_register", body.skill_id)
    return {"ok": True, "skill_id": body.skill_id}


@router.post("/{skill_id}/disable")
def disable(skill_id: str):
    db.execute("UPDATE skills SET status='disabled' WHERE skill_id=?", (skill_id,))
    db.audit("system", "skill_disable", skill_id)
    return {"ok": True}


@router.get("")
def list_skills():
    rows = db.query_all("SELECT skill_id, name, description, param_schema, provider_node, status FROM skills WHERE status='active'")
    for r in rows:
        r["param_schema"] = json.loads(r.get("param_schema") or "{}")
    return {"ok": True, "skills": rows}


@router.get("/{skill_id}")
def get_skill(skill_id: str):
    row = db.query_one("SELECT * FROM skills WHERE skill_id=?", (skill_id,))
    if not row:
        raise HTTPException(status_code=404, detail="skill not found")
    row["param_schema"] = json.loads(row.get("param_schema") or "{}")
    return {"ok": True, "skill": row}


@router.post("/call")
def call_skill(body: ToolCall):
    """技能调用别名：复用 /tools/call 的审批链路，不直接执行工具。"""
    from .tools import call as _tool_call
    return _tool_call(body)
