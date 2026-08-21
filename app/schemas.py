"""Pydantic 请求/响应模型。底座只校验结构，不理解业务。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRegister(BaseModel):
    agent_id: str
    name: str
    role: str = "worker"  # worker | toolnode
    capabilities: list[str] = Field(default_factory=list)
    endpoint_url: str = ""
    token: str = ""
    auto_reply: dict[str, Any] = Field(default_factory=dict)


class AgentHeartbeat(BaseModel):
    agent_id: str


class AgentUpdate(BaseModel):
    name: str | None = None
    capabilities: list[str] | None = None
    endpoint_url: str | None = None
    auto_reply: dict[str, Any] | None = None
    system_prompt: str | None = None


class AgentAutoReply(BaseModel):
    """子 Agent 自动应答配置：收到任务消息时按模板自动回复。"""
    enabled: bool = True
    reply_template: str = "收到，{from}。任务「{task}」已记录，处理中…"


class TaskCreate(BaseModel):
    title: str
    description: str = ""


class TaskBroadcast(BaseModel):
    task_id: str
    manager_id: str


class TaskAssign(BaseModel):
    task_id: str
    agent_id: str
    role: str = "member"


class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending|broadcasting|in_progress|done|failed|cancelled


class MessageSend(BaseModel):
    from_agent: str
    channel_type: str  # private | group | task
    to_agent: str = ""
    task_id: str = ""
    content: str


class MemoryWrite(BaseModel):
    agent_id: str
    domain: str  # agent:<id> | task:<id> | global
    mem_key: str
    content: str


class MemoryDelete(BaseModel):
    agent_id: str
    domain: str
    mem_key: str


class ApprovalDecision(BaseModel):
    manager_id: str
    request_id: str
    approve: bool


class SkillRegister(BaseModel):
    skill_id: str
    name: str
    description: str = ""
    param_schema: dict[str, Any] = Field(default_factory=dict)
    endpoint_url: str
    provider_node: str = ""


class ToolCall(BaseModel):
    agent_id: str
    skill_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class ManagerSet(BaseModel):
    agent_id: str


class DelegateRequest(BaseModel):
    """Agent 委托调用：父 Agent 给目标子 Agent 派任务。

    目标子 Agent 若开了自动应答(auto_reply)，底座立即生成应答并写回消息，
    形成「调用 → 应答」闭环；未开则消息进其收件箱，等人工/后续处理。
    """
    from_agent: str
    to_agent: str
    task_content: str


# ---- v0.2 工作流 ----


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    definition: dict[str, Any] = Field(
        default_factory=lambda: {"nodes": [], "edges": []}
    )


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict[str, Any] | None = None
    status: str | None = None  # active | disabled


class WorkflowStepDecision(BaseModel):
    approve: bool
    comment: str = ""
