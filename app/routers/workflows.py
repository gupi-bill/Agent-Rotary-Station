"""v0.2 P0：可视化工作流后端。

约束：
- 仅手动触发
- DAG 执行器不自建业务逻辑，只按节点类型依次调用 v0.1 原有 API
- 工具/记忆节点依然走 manager 审批链路，不直接读写数据库
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from .. import config, db
from ..schemas import WorkflowCreate, WorkflowUpdate

router = APIRouter(prefix="/workflows", tags=["workflows"])

NODE_TYPES = {"agent", "tool", "memory_write", "memory_read", "approval"}


def _now() -> float:
    return time.time()


def _parse_def(definition: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = definition.get("nodes") or []
    edges = definition.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HTTPException(status_code=400, detail="definition.nodes/edges must be lists")
    return nodes, edges


def _validate_definition(definition: dict[str, Any]) -> None:
    nodes, edges = _parse_def(definition)
    ids = {n.get("id") for n in nodes}
    if len(ids) != len(nodes):
        raise HTTPException(status_code=400, detail="duplicate node id")
    for n in nodes:
        if n.get("type") not in NODE_TYPES:
            raise HTTPException(status_code=400, detail=f"invalid node type: {n.get('type')}")
    for e in edges:
        if e.get("source") not in ids or e.get("target") not in ids:
            raise HTTPException(status_code=400, detail="edge points to unknown node")


def _run_node(node: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """执行单个节点，只调用 v0.1 已有 API。"""
    typ = node.get("type")
    data = node.get("data") or {}
    if typ == "agent":
        agent_id = data.get("agent_id")
        if not agent_id:
            raise ValueError("agent node missing agent_id")
        content = data.get("content", "")
        task_id = ctx.get("task_id", "")
        from ..schemas import MessageSend
        from . import messages
        r = messages.send(MessageSend(
            from_agent=agent_id,
            channel_type="task" if task_id else "private",
            to_agent=data.get("to_agent", agent_id),
            task_id=task_id,
            content=content,
        ))
        return {"ok": True, "result": r}
    if typ == "tool":
        from ..schemas import ToolCall
        from . import skills
        r = skills.call_skill(ToolCall(
            agent_id=data.get("owner_agent_id") or ctx.get("trigger_by", "workflow"),
            skill_id=data.get("skill_id", ""),
            params=data.get("params", {}),
        ))
        return {"ok": True, "result": r}
    if typ in ("memory_write", "memory_read"):
        from ..schemas import MemoryWrite
        from . import memories
        domain = data.get("domain", "global")
        mem_key = data.get("mem_key", "")
        owner = data.get("owner_agent_id")
        if not owner:
            raise ValueError(f"{typ} node missing owner_agent_id")
        if typ == "memory_write":
            r = memories.write(MemoryWrite(
                agent_id=owner,
                domain=domain,
                mem_key=mem_key,
                content=data.get("content", ""),
            ))
        else:
            r = memories.read(
                reader=owner,
                domain=domain,
                mem_key=mem_key or None,
            )
        return {"ok": True, "result": r}
    if typ == "approval":
        # 审批节点：返回 pending 信号，由执行器挂起工作流
        return {"ok": True, "pending": True, "detail": "approval node waiting for decision"}
    raise HTTPException(status_code=400, detail=f"unhandled node type: {typ}")


def _topo_order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kahn 拓扑排序，返回按执行顺序的节点列表。"""
    from collections import defaultdict, deque
    in_deg = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        adj[e["source"]].append(e["target"])
        in_deg[e["target"]] = in_deg.get(e["target"], 0) + 1
    q = deque([n for n in nodes if in_deg.get(n["id"], 0) == 0])
    ordered: list[dict[str, Any]] = []
    by_id = {n["id"]: n for n in nodes}
    while q:
        cur = q.popleft()
        ordered.append(cur)
        for nxt in adj.get(cur["id"], []):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                q.append(by_id[nxt])
    if len(ordered) != len(nodes):
        raise HTTPException(status_code=400, detail="workflow definition contains a cycle")
    return ordered


def _run_workflow_from(wf: dict[str, Any], run_id: str, trigger_by: str,
                       start_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """执行一段节点序列，遇审批节点挂起。"""
    ctx = {"task_id": "", "trigger_by": trigger_by, "workflow_id": wf["workflow_id"]}
    results: list[dict[str, Any]] = []
    for node in start_nodes:
        db.execute("UPDATE workflow_runs SET current_node=? WHERE run_id=?", (node["id"], run_id))
        try:
            out = _run_node(node, ctx)
            results.append({"node": node["id"], "ok": True, "result": out})
            if node["type"] == "agent" and out.get("result", {}).get("ok"):
                ctx["task_id"] = out["result"].get("msg_id", "") or ctx["task_id"]
            if node["type"] == "approval" and out.get("pending"):
                # 挂起：保存剩余节点供恢复
                remaining = json.dumps(start_nodes[len(results):], ensure_ascii=False)
                db.execute(
                    "UPDATE workflow_runs SET status='awaiting_approval', current_node=?, result=? WHERE run_id=?",
                    (node["id"], remaining, run_id),
                )
                return {"ok": True, "run_id": run_id, "status": "awaiting_approval",
                        "node": node["id"], "results": results}
        except Exception as exc:  # noqa: BLE001
            db.execute(
                "UPDATE workflow_runs SET status='failed', error=?, finished_at=? WHERE run_id=?",
                (str(exc), _now(), run_id),
            )
            results.append({"node": node["id"], "ok": False, "error": str(exc)})
            return {"ok": False, "run_id": run_id, "status": "failed",
                    "error": str(exc), "results": results}
    db.execute(
        "UPDATE workflow_runs SET status='done', result=?, current_node='', finished_at=? WHERE run_id=?",
        (json.dumps(results, ensure_ascii=False), _now(), run_id),
    )
    db.audit(trigger_by, "workflow_run_done", wf["workflow_id"], {"run_id": run_id})
    return {"ok": True, "run_id": run_id, "status": "done", "results": results}


def _execute_workflow(wf: dict[str, Any], trigger_by: str) -> dict[str, Any]:
    """执行 DAG，返回 run 状态。敏感操作走 v0.1 审批 API。"""
    if config.EMERGENCY_BLOCK:
        return {"ok": False, "status": "blocked", "error": "emergency block is active"}
    definition = json.loads(wf["definition"] or '{"nodes":[],"edges":[]}')
    nodes, edges = _parse_def(definition)
    ordered = _topo_order(nodes, edges)
    run_id = db.new_id("wfrun")
    db.execute(
        "INSERT INTO workflow_runs (run_id, workflow_id, status, created_at) VALUES (?, ?, 'running', ?)",
        (run_id, wf["workflow_id"], _now()),
    )
    return _run_workflow_from(wf, run_id, trigger_by, ordered)


@router.post("/create")
def create(body: WorkflowCreate):
    _validate_definition(body.definition)
    workflow_id = db.new_id("wf")
    now = _now()
    db.execute(
        "INSERT INTO workflows (workflow_id, name, description, definition, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'active', ?, ?)",
        (workflow_id, body.name, body.description,
         json.dumps(body.definition, ensure_ascii=False), now, now),
    )
    db.audit("human", "workflow_create", workflow_id, {"name": body.name})
    return {"ok": True, "workflow_id": workflow_id}


@router.get("")
def list_workflows():
    rows = db.query_all("SELECT * FROM workflows ORDER BY id DESC")
    for r in rows:
        r["definition"] = json.loads(r.get("definition") or '{"nodes":[],"edges":[]}')
    return {"ok": True, "workflows": rows}


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    wf = db.query_one("SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,))
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    wf["definition"] = json.loads(wf.get("definition") or '{"nodes":[],"edges":[]}')
    return {"ok": True, "workflow": wf}


@router.post("/{workflow_id}/update")
def update(workflow_id: str, body: WorkflowUpdate):
    wf = db.query_one("SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,))
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    if body.definition is not None:
        _validate_definition(body.definition)
    name = body.name if body.name is not None else wf["name"]
    desc = body.description if body.description is not None else wf["description"]
    definition = (json.dumps(body.definition, ensure_ascii=False) if body.definition is not None
                  else wf["definition"])
    status = body.status if body.status is not None else wf["status"]
    db.execute(
        "UPDATE workflows SET name=?, description=?, definition=?, status=?, updated_at=? WHERE workflow_id=?",
        (name, desc, definition, status, _now(), workflow_id),
    )
    db.audit("human", "workflow_update", workflow_id)
    return {"ok": True}


@router.post("/{workflow_id}/delete")
def delete(workflow_id: str):
    db.execute("DELETE FROM workflows WHERE workflow_id=?", (workflow_id,))
    db.audit("human", "workflow_delete", workflow_id)
    return {"ok": True}


@router.post("/{workflow_id}/run")
def run(workflow_id: str, trigger_by: str = "human"):
    """手动触发工作流。"""
    wf = db.query_one("SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,))
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    if wf["status"] != "active":
        raise HTTPException(status_code=409, detail="workflow is disabled")
    return _execute_workflow(wf, trigger_by)


@router.get("/runs/{run_id}")
def run_status(run_id: str):
    row = db.query_one("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,))
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "run": row}


@router.get("/{workflow_id}/runs")
def list_runs(workflow_id: str):
    rows = db.query_all(
        "SELECT * FROM workflow_runs WHERE workflow_id=? ORDER BY id DESC",
        (workflow_id,),
    )
    return {"ok": True, "runs": rows}


@router.post("/runs/{run_id}/approve")
def approve_run(run_id: str, manager_id: str = "human"):
    """审批通过：继续执行挂起工作流的剩余节点。"""
    run = db.query_one("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,))
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="run is not awaiting approval")
    remaining = json.loads(run["result"] or "[]")
    wf = db.query_one("SELECT * FROM workflows WHERE workflow_id=?", (run["workflow_id"],))
    if not wf:
        raise HTTPException(status_code=404, detail="workflow not found")
    db.execute("UPDATE workflow_runs SET status='running', result='', current_node='' WHERE run_id=?", (run_id,))
    return _run_workflow_from(wf, run_id, manager_id, remaining)


@router.post("/runs/{run_id}/deny")
def deny_run(run_id: str, manager_id: str = "human"):
    """审批拒绝：终止工作流。"""
    run = db.query_one("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,))
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="run is not awaiting approval")
    db.execute("UPDATE workflow_runs SET status='denied', current_node='', finished_at=? WHERE run_id=?",
               (_now(), run_id))
    db.audit(manager_id, "workflow_run_denied", run["workflow_id"], {"run_id": run_id})
    return {"ok": True, "run_id": run_id, "status": "denied"}
