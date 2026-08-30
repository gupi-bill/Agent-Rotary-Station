"""v3 P0 NATS 通信层封装（可选启用，不可达自动降级）。

设计原则：
- 底座仍是纯调度层，本模块只负责"消息送达"，不包含任何业务决策。
- NATS 未启用/不可达时，所有 publish 返回 False 并静默降级，
  调用方继续走原有 HTTP / SQLite 通道，保证系统可用性。
- 紧急刹车由路由层统一拦截，本模块不单独放行。

实现说明：
- 采用"每消息短连接 + flush + drain"模式，避免 nats-py 连接对象
  跨 asyncio 事件循环使用导致的绑定冲突；低流量场景足够可靠。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from . import config

logger = logging.getLogger("ars.nats")

# Subject 常量：与 docs/ARCHITECTURE_V3.md 第 4.1 节保持一致
S_AGENT_INBOX = "station.agents.{agent_id}.inbox"
S_TASK_BROADCAST = "station.tasks.{task_id}.broadcast"
S_TASK_GRAB = "station.tasks.{task_id}.grab"
S_TASK_CHAT = "station.tasks.{task_id}.chat"
S_APPROVAL_INBOX = "station.approval.inbox"
S_APPROVAL_RESULT = "station.approval.result.{agent_id}"
S_TOOLS_QUEUE = "station.tools.queue"
S_SKILLS_ANNOUNCE = "station.skills.announce"
S_EMERGENCY_BLOCK = "station.emergency.block"
S_AGENT_HEARTBEAT = "station.agents.heartbeat"


def _fmt(subject_tpl: str, **kwargs: Any) -> str:
    return subject_tpl.format(**kwargs)


def _publish_once(subject: str, data: bytes) -> bool:
    """建立短连接发一条消息；任何异常返回 False。"""
    try:
        import nats  # 延迟导入，未安装时降级
    except Exception:
        return False

    async def _go():
        nc = await nats.connect(
            config.NATS_URL,
            connect_timeout=config.NATS_CONNECT_TIMEOUT,
            allow_reconnect=False,
            verbose=False,
        )
        try:
            await nc.publish(subject, data)
            await nc.flush()
        finally:
            await nc.drain()

    try:
        asyncio.run(_go())
        return True
    except Exception as exc:
        logger.debug("NATS publish failed: %s", exc)
        return False


def is_available() -> bool:
    """探测 NATS 是否可用（短连接探活）。"""
    if not config.NATS_ENABLED:
        return False
    return _publish_once("station.health.probe", b"{}")


def publish(subject: str, payload: dict[str, Any]) -> bool:
    """发布一条消息；失败返回 False，由调用方降级。"""
    if not config.NATS_ENABLED:
        return False
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _publish_once(subject, data)


def publish_task_broadcast(task_id: str, payload: dict[str, Any]) -> bool:
    return publish(_fmt(S_TASK_BROADCAST, task_id=task_id), payload)


def publish_task_grab(task_id: str, payload: dict[str, Any]) -> bool:
    return publish(_fmt(S_TASK_GRAB, task_id=task_id), payload)


def publish_agent_inbox(agent_id: str, payload: dict[str, Any]) -> bool:
    return publish(_fmt(S_AGENT_INBOX, agent_id=agent_id), payload)


def publish_approval(payload: dict[str, Any]) -> bool:
    return publish(S_APPROVAL_INBOX, payload)


def publish_emergency_block(active: bool) -> bool:
    return publish(S_EMERGENCY_BLOCK, {"active": active})
