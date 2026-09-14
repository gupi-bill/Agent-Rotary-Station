"""v0.2 tests: workflow + P1."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, db
from app.routers import agents, skills, tools, workflows
from app.schemas import (
    AgentRegister,
    ManagerSet,
    SkillRegister,
    ToolCall,
    WorkflowCreate,
    ApprovalDecision,
)

config.EMERGENCY_BLOCK = False


def clean():
    db.init_db()
    for t in ["workflow_runs", "workflows", "tool_queue", "tool_requests",
              "memory_approvals", "memories", "task_members", "tasks",
              "messages", "skills", "audit_logs", "agents"]:
        db.execute(f"DELETE FROM {t}")


def test_heartbeat():
    clean()
    agents.register(AgentRegister(agent_id="h1", name="H1"))
    db.execute("UPDATE agents SET last_seen=1.0 WHERE agent_id=?", ("h1",))
    n = db.mark_stale_agents_offline(config.AGENT_HEARTBEAT_TIMEOUT)
    assert db.get_agent("h1")["status"] == "offline"
    assert n >= 1
    print("OK heartbeat")


def test_approval():
    clean()
    agents.register(AgentRegister(agent_id="a1", name="A1"))
    agents.register(AgentRegister(agent_id="mgr", name="MGR"))
    agents.set_manager(ManagerSet(agent_id="mgr"))
    w = workflows.create(WorkflowCreate(
        name="approval-wf",
        definition={
            "nodes": [
                {"id": "n1", "type": "agent", "data": {"agent_id": "a1", "content": "start"}},
                {"id": "n2", "type": "approval", "data": {}},
                {"id": "n3", "type": "agent", "data": {"agent_id": "a1", "content": "after"}},
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
        },
    ))
    r = workflows.run(w["workflow_id"], trigger_by="human")
    assert r["status"] == "awaiting_approval", str(r)
    r2 = workflows.approve_run(r["run_id"], manager_id="mgr")
    assert r2["status"] == "done", str(r2)
    print("OK approval")


def test_queue():
    clean()
    agents.register(AgentRegister(agent_id="tn1", name="ToolNode", role="toolnode"))
    agents.register(AgentRegister(agent_id="mgr", name="MGR"))
    agents.set_manager(ManagerSet(agent_id="mgr"))
    skills.register(SkillRegister(
        skill_id="q_echo", name="QueueEcho", endpoint_url="http://127.0.0.1:9/nope",
        provider_node="tn1",
    ))
    r = tools.call(ToolCall(agent_id="a1", skill_id="q_echo", params={}))
    d = tools.decide(ApprovalDecision(manager_id="mgr", request_id=r["request_id"], approve=True))
    assert d["status"] in ("queued", "failed"), str(d)
    print("OK queue")


if __name__ == "__main__":
    test_heartbeat()
    test_approval()
    test_queue()
    print("V02_ALL_PASS")
