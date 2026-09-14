"""v0.2 红线回归：workflow 的 memory/tool 节点必须走审批，环检测，紧急刹车。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, db
from app.routers import agents, memories, skills, workflows
from app.schemas import (
    AgentRegister,
    ManagerSet,
    SkillRegister,
    WorkflowCreate,
    ApprovalDecision,
)

config.EMERGENCY_BLOCK = False
memories.APPROVAL_WAIT_TIMEOUT = 0.3  # 测试加速，不影响 prod 默认 30s


def clean():
    db.init_db()
    for t in ["workflow_runs", "workflows", "tool_queue", "tool_requests",
              "memory_approvals", "memories", "task_members", "tasks",
              "messages", "skills", "audit_logs", "agents"]:
        db.execute(f"DELETE FROM {t}")


def test_wf_memory_write_via_approval():
    """memory_write 节点必须生成审批单，manager 放行后才落库（红线）。"""
    clean()
    agents.register(AgentRegister(agent_id="m1", name="M"))
    agents.set_manager(ManagerSet(agent_id="m1"))
    agents.register(AgentRegister(agent_id="w1", name="W"))
    wf = workflows.create(WorkflowCreate(name="mw", definition={
        "nodes": [{"id": "n1", "type": "memory_write",
                   "data": {"owner_agent_id": "w1", "domain": "agent:w1",
                            "mem_key": "k", "content": "v"}}],
        "edges": [],
    }))
    # memory 节点走 v0.1 异步审批：run 返回后 pending 审批单应已生成
    workflows.run(wf["workflow_id"], trigger_by="human")
    ra = db.query_one("SELECT * FROM memory_approvals WHERE status='pending' ORDER BY id DESC")
    assert ra is not None, "memory_write node must create a pending approval"
    memories.decide(ApprovalDecision(manager_id="m1", request_id=ra["request_id"], approve=True))
    mem = db.query_one("SELECT * FROM memories WHERE domain='agent:w1' AND mem_key='k'")
    assert mem is not None and mem["content"] == "v", "memory not persisted after approval"
    print("OK wf memory_write via approval -> persisted")


def test_wf_tool_node_pending():
    """tool 节点只生成 pending 审批，不直接执行（红线）。"""
    clean()
    agents.register(AgentRegister(agent_id="m1", name="M"))
    agents.set_manager(ManagerSet(agent_id="m1"))
    skills.register(SkillRegister(
        skill_id="t1", name="T", provider_node="tn", endpoint_url="http://127.0.0.1:9/x"))
    wf = workflows.create(WorkflowCreate(name="tn", definition={
        "nodes": [{"id": "n1", "type": "tool",
                   "data": {"skill_id": "t1", "params": {}}}],
        "edges": [],
    }))
    workflows.run(wf["workflow_id"], trigger_by="human")
    tr = db.query_one("SELECT * FROM tool_requests WHERE status='pending' ORDER BY id DESC")
    assert tr is not None, "tool node must create a pending tool_request"
    print("OK wf tool node -> pending approval (no direct exec)")


def test_wf_cycle_rejected():
    """含环的定义在运行时必须被拓扑排序拒绝。"""
    clean()
    agents.register(AgentRegister(agent_id="x", name="X"))
    wf = workflows.create(WorkflowCreate(name="cyc", definition={
        "nodes": [
            {"id": "a", "type": "agent", "data": {"agent_id": "x", "content": "1"}},
            {"id": "b", "type": "agent", "data": {"agent_id": "x", "content": "2"}},
        ],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }))
    assert wf["ok"]
    caught = False
    try:
        workflows.run(wf["workflow_id"], trigger_by="human")
    except Exception as e:  # noqa: BLE001
        caught = "cycle" in str(e).lower()
    assert caught, "cycle workflow must be rejected at run"
    print("OK wf cycle rejected at run")


def test_emergency_block():
    """紧急刹车激活时，任何工作流运行必须被阻断。"""
    clean()
    agents.register(AgentRegister(agent_id="x", name="X"))
    wf = workflows.create(WorkflowCreate(name="eb", definition={
        "nodes": [{"id": "n1", "type": "agent", "data": {"agent_id": "x", "content": "1"}}],
        "edges": [],
    }))
    config.EMERGENCY_BLOCK = True
    r = workflows.run(wf["workflow_id"], trigger_by="human")
    config.EMERGENCY_BLOCK = False
    assert r["status"] == "blocked", str(r)
    print("OK emergency block halts workflow")


if __name__ == "__main__":
    test_wf_memory_write_via_approval()
    test_wf_tool_node_pending()
    test_wf_cycle_rejected()
    test_emergency_block()
    print("WF_CORE_ALL_PASS")
