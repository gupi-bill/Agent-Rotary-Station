"""定时调度：cron 增删改、启停、手动触发、执行历史 + 后台调度线程。"""
from __future__ import annotations

import json
import threading
import time

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter(prefix="/crons", tags=["crons"])


def _run_cron_action(cron: dict, trigger: str = "schedule") -> dict:
    """执行一个 cron 的动作（message=给目标 Agent 发消息 / workflow=触发工作流运行）。"""
    cron_id = cron["cron_id"]
    try:
        payload = json.loads(cron.get("payload") or "{}")
    except Exception:
        payload = {}
    run_id = db.new_id("crrun")
    try:
        if cron.get("action") == "workflow":
            # 触发工作流运行
            wid = cron.get("target") or ""
            from .workflows import _execute_workflow
            wf = db.query_one("SELECT * FROM workflows WHERE workflow_id=?", (wid,))
            if not wf:
                detail = f"workflow {wid} not found"
                status = "error"
            else:
                try:
                    _execute_workflow(wf, "cron")
                    detail = f"workflow {wid} triggered"
                    status = "success"
                except Exception as ex:
                    detail = f"workflow {wid} error: {ex}"
                    status = "error"
        else:
            # 默认：向目标 Agent 发消息
            to_agent = cron.get("target") or ""
            content = str(payload.get("content") or f"定时任务「{cron.get('name', '')}」触发")
            db.execute(
                "INSERT INTO messages (msg_id, channel_type, from_agent, to_agent, task_id, content, created_at) "
                "VALUES (?, 'private', 'cron', ?, '', ?, ?)",
                (db.new_id("msg"), to_agent, content, db.now()),
            )
            detail = f"message -> {to_agent}"
            status = "success"
        db.execute(
            "INSERT INTO cron_runs (run_id, cron_id, status, detail, triggered_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, cron_id, status, detail, trigger, db.now()),
        )
        db.execute("UPDATE crons SET last_run_at=? WHERE cron_id=?", (db.now(), cron_id))
        return {"ok": True, "run_id": run_id, "status": status, "detail": detail}
    except Exception as e:
        db.execute(
            "INSERT INTO cron_runs (run_id, cron_id, status, detail, triggered_by, created_at) "
            "VALUES (?, ?, 'error', ?, ?, ?)",
            (run_id, cron_id, str(e), trigger, db.now()),
        )
        return {"ok": False, "run_id": run_id, "status": "error", "detail": str(e)}


def scheduler_loop(stop: threading.Event, interval: float = 1.0) -> None:
    """后台调度线程：每秒扫一次，把到期的启用 cron 执行掉。"""
    while not stop.is_set():
        try:
            now = db.now()
            rows = db.query_all(
                "SELECT * FROM crons WHERE enabled=1 AND (next_run_at IS NULL OR next_run_at<=?)",
                (now,))
            for cron in rows:
                _run_cron_action(cron, "schedule")
                db.execute("UPDATE crons SET next_run_at=? WHERE cron_id=?",
                           (now + float(cron.get("interval_sec") or 3600), cron["cron_id"]))
        except Exception:
            pass
        stop.wait(interval)


@router.get("")
def list_crons():
    rows = db.query_all("SELECT * FROM crons ORDER BY created_at DESC")
    return {"ok": True, "crons": rows}


@router.post("/create")
def create_cron(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    cron_id = db.new_id("cron")
    interval = int(body.get("interval_sec") or 3600)
    ts = db.now()
    db.execute(
        "INSERT INTO crons (cron_id, name, schedule, interval_sec, action, target, payload, enabled, next_run_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cron_id, name, body.get("schedule", f"every {interval}s"), interval,
         body.get("action", "message"), body.get("target", ""),
         json.dumps(body.get("payload", {}), ensure_ascii=False),
         1 if body.get("enabled", True) else 0, ts + interval, ts, ts),
    )
    db.audit("human", "cron_create", cron_id, {"name": name})
    return {"ok": True, "cron_id": cron_id}


@router.post("/{cron_id}/toggle")
def toggle_cron(cron_id: str):
    row = db.query_one("SELECT * FROM crons WHERE cron_id=?", (cron_id,))
    if not row:
        raise HTTPException(status_code=404, detail="cron not found")
    new_enabled = 0 if row.get("enabled") else 1
    db.execute("UPDATE crons SET enabled=? WHERE cron_id=?", (new_enabled, cron_id))
    db.audit("human", "cron_toggle", cron_id, {"enabled": bool(new_enabled)})
    return {"ok": True, "cron_id": cron_id, "enabled": bool(new_enabled)}


@router.post("/{cron_id}/run")
def run_cron_now(cron_id: str):
    row = db.query_one("SELECT * FROM crons WHERE cron_id=?", (cron_id,))
    if not row:
        raise HTTPException(status_code=404, detail="cron not found")
    return _run_cron_action(row, "manual")


@router.post("/{cron_id}/delete")
def delete_cron(cron_id: str):
    if not db.query_one("SELECT 1 FROM crons WHERE cron_id=?", (cron_id,)):
        raise HTTPException(status_code=404, detail="cron not found")
    db.execute("DELETE FROM crons WHERE cron_id=?", (cron_id,))
    db.execute("DELETE FROM cron_runs WHERE cron_id=?", (cron_id,))
    db.audit("human", "cron_delete", cron_id)
    return {"ok": True}


@router.get("/{cron_id}/history")
def cron_history(cron_id: str, limit: int = 30):
    rows = db.query_all(
        "SELECT * FROM cron_runs WHERE cron_id=? ORDER BY id DESC LIMIT ?",
        (cron_id, limit))
    return {"ok": True, "runs": rows}
