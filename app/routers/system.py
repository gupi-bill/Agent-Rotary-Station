"""系统：健康检查、审计日志、紧急刹车、心跳超时、工具队列、SSE 事件流。"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .. import config, db, events, nats_bus

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    return {"ok": True, "station": "Agent-Rotary-Station",
            "emergency_block": config.EMERGENCY_BLOCK}


@router.get("/stats")
def stats():
    """总览统计：在线 Agent / 待审批(记忆+工具) / 运行中工作流 / 任务 / 紧急刹车。

    统计全部在底座完成，前端只做展示（供 BlueDeer new_ui 监控面板）。
    """
    def _count(sql: str) -> int:
        try:
            row = db.query_one(sql)
            return int((row or {}).get("c") or 0)
        except Exception:
            return 0

    return {"ok": True, "stats": {
        "agents_total": _count("SELECT COUNT(*) c FROM agents"),
        "agents_online": _count("SELECT COUNT(*) c FROM agents WHERE status='online'"),
        "approvals_pending": _count("SELECT COUNT(*) c FROM memory_approvals WHERE status='pending'"),
        "tool_pending": _count("SELECT COUNT(*) c FROM tool_requests WHERE status='pending'"),
        "workflows_active": _count("SELECT COUNT(*) c FROM workflows WHERE status='active'"),
        "workflows_running": _count(
            "SELECT COUNT(*) c FROM workflow_runs WHERE status IN ('running','awaiting_approval','pending')"
        ),
        "tasks_pending": _count(
            "SELECT COUNT(*) c FROM tasks WHERE status IN ('pending','broadcasting','assigned')"
        ),
        "messages_total": _count("SELECT COUNT(*) c FROM messages"),
        "emergency_block": bool(config.EMERGENCY_BLOCK),
    }}


@router.get("/audit-logs")
def audit_logs(limit: int = 100, actor: str | None = None):
    if actor:
        rows = db.query_all(
            "SELECT * FROM audit_logs WHERE actor=? ORDER BY id DESC LIMIT ?",
            (actor, limit),
        )
    else:
        rows = db.query_all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        try:
            r["detail"] = json.loads(r.get("detail") or "{}")
        except json.JSONDecodeError:
            pass
    return {"ok": True, "logs": rows}


@router.get("/emergency-block")
def get_block():
    return {"ok": True, "emergency_block": config.EMERGENCY_BLOCK}


@router.post("/emergency-block/toggle")
def toggle_block(active: bool = True):
    """人类最高紧急拦截：修改 config 模块级开关，所有路由实时生效。"""
    config.EMERGENCY_BLOCK = active
    db.audit("human", "emergency_block_toggle", str(active))
    nats_bus.publish_emergency_block(active)
    events.publish("emergency_block", {"active": active})
    return {"ok": True, "emergency_block": config.EMERGENCY_BLOCK}


@router.post("/heartbeat-check")
def heartbeat_check():
    """手动触发心跳超时检查：超时 Agent 置为 offline。"""
    count = db.mark_stale_agents_offline(config.AGENT_HEARTBEAT_TIMEOUT)
    if count:
        events.publish("agents_offline", {"count": count})
    return {"ok": True, "marked_offline": count}


# ---- 控制台设置（前端设置中心存底座，真实生效） ----


def _get_settings() -> dict:
    rows = db.query_all("SELECT key, value FROM settings")
    out: dict = {}
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except Exception:
            out[r["key"]] = r["value"]
    return out


@router.get("/settings")
def get_settings():
    """控制台设置（默认自动应答模板等），前端设置中心读写。"""
    return {"ok": True, "settings": _get_settings()}


@router.post("/settings")
def save_settings(body: dict):
    """合并保存设置（只写传入的 key）。"""
    if not isinstance(body, dict):
        return {"ok": False, "error": "body must be object"}
    ts = db.now()
    for k, v in body.items():
        db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (k, json.dumps(v, ensure_ascii=False), ts),
        )
    db.audit("human", "settings_save", ",".join(body.keys()))
    return {"ok": True, "settings": _get_settings()}


@router.get("/probe-models")
def probe_models(api_base: str = "", api_key: str = ""):
    """真实探测模型列表。

    api_base 为空 → 探测本地 Ollama(11434 /api/tags)；
    否则按 OpenAI 兼容端点 GET {api_base}/models（支持硅基流动/DeepSeek/GitHub Models/智谱）。
    """
    import urllib.request

    if not api_base:
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return {"ok": True, "source": "ollama", "models": models}
        except Exception as e:
            return {"ok": False, "source": "ollama", "models": [], "error": f"Ollama 未运行: {e}"}

    base = api_base.rstrip("/")
    url = base + "/models"
    try:
        req = urllib.request.Request(url, method="GET")
        if api_key:
            req.add_header("Authorization", "Bearer " + api_key)
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        if not models and isinstance(data, dict):
            # 兼容 {models:[...]} 形态
            models = [m.get("id", m if isinstance(m, str) else "") for m in data.get("models", [])]
        return {"ok": True, "source": base, "models": models}
    except Exception as e:
        return {"ok": False, "source": base, "models": [], "error": str(e)}


@router.post("/tool-queue/process")
def tool_queue_process():
    """手动触发待补发工具队列。"""
    from . import tools
    result = tools.queue_process()
    events.publish("tool_queue_processed", result)
    return result


@router.get("/events")
async def events_stream():
    """SSE 实时事件流（借鉴 PocketBase 实时订阅理念）。

    WebUI 用 EventSource 订阅，获得任务/审批/记忆/工具/紧急刹车等
    状态变更的实时推送；数据仍以 SQLite 为唯一主存储。
    """
    queue = events.subscribe()

    async def gen():
        try:
            # 先补发最近事件，避免断线重连丢历史
            for ev in events.recent_events(limit=50):
                yield events.sse_format(ev)
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield events.sse_format(ev)
                except asyncio.TimeoutError:
                    # 心跳注释行，保持连接
                    yield ": ping\n\n"
        finally:
            events.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
