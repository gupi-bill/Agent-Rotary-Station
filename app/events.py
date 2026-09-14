"""v3 P1 借鉴 PocketBase 实时订阅理念的 SSE 事件总线。

定位：
- ARS 主存储仍是 SQLite，审批链路不变，本模块不写库、不改业务。
- 关键业务动作发生后，向内存事件总线广播一条事件，
  WebUI 通过 /system/events SSE 端点订阅，获得"镜像面板"的实时刷新体验。
- 借鉴 PocketBase Admin UI 可视化理念，但不引入 PocketBase 依赖。
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import Any, Deque

# 每个事件类型最多保留的最近事件数
_MAX_EVENTS = 200

# 环形缓冲：新事件进来，旧事件溢出
_events: Deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)

# 订阅者：每个订阅是 {queue}
_subscribers: list[dict[str, Any]] = []


def _now() -> float:
    return time.time()


def publish(event_type: str, payload: dict[str, Any]) -> None:
    """发布一条事件。事件只广播给订阅者，不阻塞调用方。"""
    event = {
        "seq": len(_events),
        "ts": _now(),
        "type": event_type,
        "data": payload,
    }
    _events.append(event)
    _broadcast(event)


def _broadcast(event: dict[str, Any]) -> None:
    """把事件投递给所有订阅者队列；队列满则丢弃（不阻塞）。"""
    dead = []
    for sub in _subscribers:
        try:
            sub["queue"].put_nowait(event)
        except asyncio.QueueFull:
            try:
                sub["queue"].get_nowait()
                sub["queue"].put_nowait(event)
            except Exception:
                pass
        except Exception:
            dead.append(sub)
    for sub in dead:
        try:
            _subscribers.remove(sub)
        except ValueError:
            pass


def subscribe() -> asyncio.Queue:
    """注册一个订阅者，返回其事件队列。"""
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    _subscribers.append({"queue": q})
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """移除订阅者。"""
    for sub in _subscribers:
        if sub["queue"] is q:
            _subscribers.remove(sub)
            return


def recent_events(limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
    """返回最近事件（用于 SSE 断线重连后的补发）。"""
    items = list(_events)
    if event_type:
        items = [e for e in items if e["type"] == event_type]
    return items[-limit:]


def sse_format(event: dict[str, Any]) -> str:
    """把事件序列化为 SSE 帧。"""
    data = json.dumps(event, ensure_ascii=False)
    return f"id: {event['seq']}\ndata: {data}\n\n"
