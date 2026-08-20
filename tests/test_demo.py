"""极简最小闭环测试：

外部 Agent 行为模拟（工作站只提供 API，不跑 Agent）：
1. a1、a2 注册；a1 设为 manager
2. a2 发私聊消息：不需要审批，直接落库
3. a2 提交写记忆请求：投递给 manager 审批，approve 后落库
4. a2 发起 skill 调用：投递给 manager 审批，approve 才执行工具

运行：
    cd Agent-Rotary-Station
    python tests\test_demo.py
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, db
from app.routers import agents, memories, messages, skills, tools
from app.schemas import (
    AgentRegister,
    ApprovalDecision,
    ManagerSet,
    MemoryWrite,
    MessageSend,
    SkillRegister,
    ToolCall,
)


def approve_latest_memory(manager_id: str, delay: float = 0.3) -> None:
    time.sleep(delay)
    req = db.query_one(
        "SELECT request_id FROM memory_approvals WHERE status='pending' ORDER BY id DESC LIMIT 1"
    )
    if req:
        memories.decide(ApprovalDecision(manager_id=manager_id, request_id=req["request_id"], approve=True))


def main() -> None:
    config.EMERGENCY_BLOCK = False
    db.init_db()
    for t in ["memory_approvals", "memories", "tool_requests", "task_members",
              "tasks", "messages", "skills", "audit_logs", "agents"]:
        db.execute(f"DELETE FROM {t}")

    # 1. 注册两个 Agent
    agents.register(AgentRegister(agent_id="a1", name="ManagerA"))
    agents.register(AgentRegister(agent_id="a2", name="WorkerA"))
    assert db.get_agent("a1") and db.get_agent("a2")
    print("[1] agent register OK")

    # 2. a1 设为 manager
    agents.set_manager(ManagerSet(agent_id="a1"))
    assert db.current_manager()["agent_id"] == "a1"
    print("[2] a1 set as manager OK")

    # 3. a2 发私聊（不需要审批，直接落库）
    r = messages.send(MessageSend(from_agent="a2", channel_type="private", to_agent="a1", content="hi"))
    assert r["ok"]
    row = db.query_one("SELECT * FROM messages WHERE msg_id=?", (r["msg_id"],))
    assert row is not None
    print("[3] private message direct (no approval) OK")

    # 4. a2 写记忆 -> 投递 manager 审批 -> approve 落库
    holder: dict = {}

    def submit_write():
        holder["result"] = memories.write(
            MemoryWrite(agent_id="a2", domain="agent:a2", mem_key="note", content="remember-me")
        )

    t_write = threading.Thread(target=submit_write)
    t_approve = threading.Thread(target=approve_latest_memory, args=("a1",))
    t_write.start(); t_approve.start(); t_write.join(); t_approve.join()
    assert holder["result"]["status"] == "approved"
    read = memories.read(reader="a2", domain="agent:a2", mem_key="note")
    assert read["memory"]["content"] == "remember-me"
    print("[4] memory write -> manager approve -> persisted OK")

    # 5. a2 发起 skill 调用 -> 只生成 pending，不直接执行
    skills.register(SkillRegister(
        skill_id="demo_echo",
        name="DemoEcho",
        provider_node="tn_demo",
        endpoint_url="http://127.0.0.1:9/unreachable",
    ))
    call = skills.call_skill(ToolCall(agent_id="a2", skill_id="demo_echo", params={"x": 1}))
    assert call["status"] == "pending"
    print("[5] skill call -> pending (not direct-executed) OK")

    # 6. manager 放行：endpoint 不可达，按 v0.1 约定返回 failed
    approve = tools.decide(ApprovalDecision(manager_id="a1", request_id=call["request_id"], approve=True))
    assert approve["status"] == "failed"
    print("[6] skill approve -> attempt exec -> failed (offline node) OK")

    print("TEST_DEMO_ALL_PASS")


if __name__ == "__main__":
    main()
