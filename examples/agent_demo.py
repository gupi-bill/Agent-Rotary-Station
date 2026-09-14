"""Agent 对接示例：演示外部 Agent 如何调用工作站的完整审批链路。

纯标准库 HTTP，零依赖。先启动工作站（run.bat）和工具（examples/mock_tool.py），再运行：
    python examples/agent_demo.py

流程：注册 manager + 员工 → 建任务 → 广播 → 员工接单 → 写记忆（审批）
      → 注册工具节点 → 员工调工具 → manager 审批执行 → 查任务详情。
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def step(msg: str):
    print("\n" + "=" * 52)
    print(msg)


def show(r):
    print(json.dumps(r, ensure_ascii=False, indent=2))


def demo():
    # 1. 注册 manager 与员工
    step("1. 注册 manager + 员工 agent")
    show(call("POST", "/agents/register", {
        "agent_id": "mgr1", "name": "调度经理", "role": "worker",
        "capabilities": ["planning", "approval"]}))
    show(call("POST", "/agents/register", {
        "agent_id": "worker1", "name": "执行员工", "role": "worker",
        "capabilities": ["coding", "writing"]}))

    # 2. 设管理岗
    step("2. 设置 mgr1 为管理岗")
    show(call("POST", "/agents/manager/set", {"agent_id": "mgr1"}))

    # 3. 员工 → manager 私聊
    step("3. 员工私聊 manager")
    show(call("POST", "/messages/send", {
        "from_agent": "worker1", "channel_type": "private",
        "to_agent": "mgr1", "content": "经理好，我准备接任务",
    }))

    # 4. 人类建任务
    step("4. 人类下发任务")
    task = call("POST", "/tasks/create", {
        "title": "写对接文档", "description": "给新人写对接说明"})
    show(task)
    task_id = task["task_id"]

    # 5. manager 广播
    step("5. manager 广播任务")
    show(call("POST", "/tasks/broadcast", {"task_id": task_id, "manager_id": "mgr1"}))

    # 6. 员工接单
    step("6. 员工接单，标记进行中")
    show(call("POST", "/tasks/assign", {"task_id": task_id, "agent_id": "worker1"}))
    show(call("POST", "/tasks/status", {"task_id": task_id, "status": "in_progress"}))

    # 7. 写记忆：后台发起（同步等待审批），主线程审批
    step("7. 写记忆（后台发起 + manager 审批）")
    result_box = {}

    def _write():
        result_box["r"] = call("POST", "/memories/write", {
            "agent_id": "worker1", "domain": "task:" + task_id,
            "mem_key": "结论", "content": "文档初稿已完成",
        })

    t = threading.Thread(target=_write, daemon=True)
    t.start()
    time.sleep(0.3)  # 等请求落成 pending
    pending = call("GET", "/memories/approvals/pending")
    req_id = pending["pending"][-1]["request_id"]
    print("审批单：", req_id)
    show(call("POST", "/memories/approvals/decide", {
        "manager_id": "mgr1", "request_id": req_id, "approve": True}))
    t.join(timeout=5)
    show(result_box.get("r", {"note": "超时未返回"}))

    # 8. 注册工具节点（mock echo）
    step("8. 工具节点注册技能")
    show(call("POST", "/skills/register", {
        "skill_id": "echo", "name": "Echo 工具",
        "param_schema": {"text": "string"},
        "endpoint_url": "http://127.0.0.1:9001",
        "provider_node": "toolnode1",
    }))

    # 9. 员工调工具（先 pending）
    step("9. 员工调工具（先 pending）")
    tool_req = call("POST", "/skills/call", {
        "agent_id": "worker1", "skill_id": "echo",
        "params": {"text": "你好，工作站"},
    })
    show(tool_req)

    # 10. manager 审批执行
    step("10. manager 审批放行（实际执行 echo）")
    show(call("POST", "/tools/approvals/decide", {
        "manager_id": "mgr1", "request_id": tool_req["request_id"], "approve": True,
    }))

    # 11. 查任务详情
    step("11. 查看任务与成员")
    show(call("GET", "/tasks/" + task_id))


if __name__ == "__main__":
    demo()
