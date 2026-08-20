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


class AgentHeartbeat(BaseModel):
    agent_id: str


class AgentUpdate(BaseModel):
    name: str | None = None
    capabilities: list[str] | None = None
    endpoint_url: str | None = None


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
