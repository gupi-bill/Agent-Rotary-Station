"""存储层：SQLite（标准库 sqlite3，零额外依赖）。
底座只做原始文本存储，不做总结/向量/RAG。
每操作短连接，check_same_thread=False 保证 FastAPI 多线程下可用。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import DB_PATH, ensure_dirs

_lock = threading.Lock()

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS agents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'worker',
    status      TEXT NOT NULL DEFAULT 'offline',
    capabilities TEXT NOT NULL DEFAULT '[]',
    endpoint_url TEXT NOT NULL DEFAULT '',
    token       TEXT NOT NULL DEFAULT '',
    last_seen   REAL NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    manager_id  TEXT NOT NULL DEFAULT '',
    created_by  TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS task_members (
    task_id    TEXT NOT NULL,
    agent_id   TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'member',
    joined_at  REAL NOT NULL,
    PRIMARY KEY (task_id, agent_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id      TEXT NOT NULL UNIQUE,
    channel_type TEXT NOT NULL,
    from_agent  TEXT NOT NULL,
    to_agent    TEXT NOT NULL DEFAULT '',
    task_id     TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL,
    mem_key     TEXT NOT NULL,
    content     TEXT NOT NULL,
    owner_agent TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    UNIQUE (domain, mem_key)
);

CREATE TABLE IF NOT EXISTS memory_approvals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id   TEXT NOT NULL UNIQUE,
    agent_id     TEXT NOT NULL,
    domain       TEXT NOT NULL,
    action       TEXT NOT NULL,
    mem_key      TEXT NOT NULL DEFAULT '',
    content      TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   REAL NOT NULL,
    decided_at   REAL,
    decided_by   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS skills (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id     TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    param_schema TEXT NOT NULL DEFAULT '{}',
    endpoint_url TEXT NOT NULL,
    provider_node TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  TEXT NOT NULL UNIQUE,
    agent_id    TEXT NOT NULL,
    skill_id    TEXT NOT NULL,
    params      TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'pending',
    manager_id  TEXT NOT NULL DEFAULT '',
    result      TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    decided_at  REAL,
    executed_at REAL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    detail     TEXT NOT NULL DEFAULT '{}',
    request_id TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_type);
CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain);
CREATE INDEX IF NOT EXISTS idx_tool_requests_status ON tool_requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(ts);

CREATE TABLE IF NOT EXISTS workflows (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id  TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    definition   TEXT NOT NULL DEFAULT '{"nodes":[],"edges":[]}',
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL UNIQUE,
    workflow_id  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    current_node TEXT NOT NULL DEFAULT '',
    result       TEXT NOT NULL DEFAULT '',
    error        TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    started_at   REAL,
    finished_at  REAL
);
CREATE TABLE IF NOT EXISTS tool_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id   TEXT NOT NULL UNIQUE,
    agent_id     TEXT NOT NULL,
    skill_id     TEXT NOT NULL,
    params       TEXT NOT NULL DEFAULT '{}',
    retries      INTEGER NOT NULL DEFAULT 0,
    max_retries  INTEGER NOT NULL DEFAULT 5,
    expire_at    REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    created_at   REAL NOT NULL,
    next_try_at  REAL NOT NULL
);

"""


def now() -> float:
    return time.time()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db() -> None:
    with _lock:
        conn = connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with _lock:
        conn = connect()
        try:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(sql, tuple(params)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def audit(actor: str, action: str, target: str = "", detail: dict | None = None,
          request_id: str = "") -> None:
    execute(
        "INSERT INTO audit_logs (ts, actor, action, target, detail, request_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now(), actor, action, target, json.dumps(detail or {}, ensure_ascii=False), request_id),
    )


def current_manager() -> dict[str, Any] | None:
    return query_one(
        "SELECT * FROM agents WHERE role='manager' AND status='online' ORDER BY id DESC LIMIT 1"
    )


def set_manager(agent_id: str) -> dict[str, Any] | None:
    execute("UPDATE agents SET role='worker' WHERE role='manager'")
    execute("UPDATE agents SET role='manager', status='online', last_seen=? WHERE agent_id=?",
            (now(), agent_id))
    audit(actor="human", action="set_manager", target=agent_id)
    return query_one("SELECT * FROM agents WHERE agent_id=?", (agent_id,))


def clear_manager() -> dict[str, Any] | None:
    """撤销管理岗：把当前 manager 降回 worker，不指派新 manager。"""
    m = current_manager()
    if m:
        execute("UPDATE agents SET role='worker' WHERE agent_id=?", (m["agent_id"],))
    audit(actor="human", action="clear_manager", target=(m or {}).get("agent_id", ""))
    return m


def get_agent(agent_id: str) -> dict[str, Any] | None:
    return query_one("SELECT * FROM agents WHERE agent_id=?", (agent_id,))


def touch_agent(agent_id: str) -> None:
    execute("UPDATE agents SET last_seen=?, status='online' WHERE agent_id=?",
            (now(), agent_id))


def can_read_memory(reader_agent: str, domain: str) -> bool:
    if domain == "global":
        return True
    if domain.startswith("agent:"):
        return domain == f"agent:{reader_agent}"
    if domain.startswith("task:"):
        task_id = domain.split(":", 1)[1]
        row = query_one(
            "SELECT 1 FROM task_members WHERE task_id=? AND agent_id=?",
            (task_id, reader_agent),
        )
        return row is not None
    return False


# ---- v0.2 P1 工具离线排队 ----

def enqueue_tool(request_id: str, agent_id: str, skill_id: str, params: str,
                 max_retries: int = 5, expire_seconds: float = 300.0) -> int:
    ts = now()
    return execute(
        "INSERT INTO tool_queue (request_id, agent_id, skill_id, params, retries, max_retries, expire_at, status, created_at, next_try_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, 'queued', ?, ?) "
        "ON CONFLICT(request_id) DO UPDATE SET status='queued', retries=0, next_try_at=excluded.next_try_at",
        (request_id, agent_id, skill_id, params, max_retries, ts + expire_seconds, ts, ts),
    )


def next_queued_tool(now_ts: float | None = None) -> dict | None:
    ts = now_ts if now_ts is not None else now()
    return query_one(
        "SELECT * FROM tool_queue WHERE status='queued' AND next_try_at<=? AND expire_at>? "
        "ORDER BY created_at ASC LIMIT 1",
        (ts, ts),
    )


def mark_queue_done(request_id: str) -> None:
    execute("DELETE FROM tool_queue WHERE request_id=?", (request_id,))


def mark_queue_failed_or_retry(request_id: str, max_retries: int, expire_at: float,
                               retry_interval: float = 5.0) -> str:
    row = query_one("SELECT * FROM tool_queue WHERE request_id=?", (request_id,))
    if not row:
        return "missing"
    if row["expire_at"] <= now():
        execute("UPDATE tool_queue SET status='expired' WHERE request_id=?", (request_id,))
        return "expired"
    if row["retries"] >= max_retries:
        execute("UPDATE tool_queue SET status='failed' WHERE request_id=?", (request_id,))
        return "failed"
    execute(
        "UPDATE tool_queue SET retries=retries+1, next_try_at=? WHERE request_id=?",
        (now() + retry_interval, request_id),
    )
    return "retry"


# ---- v0.2 P1 Agent 心跳超时 ----

def mark_stale_agents_offline(timeout_seconds: float) -> int:
    cutoff = now() - timeout_seconds
    rows = query_all(
        "SELECT agent_id FROM agents WHERE status='online' AND last_seen>0 AND last_seen<?",
        (cutoff,),
    )
    for r in rows:
        execute("UPDATE agents SET status='offline' WHERE agent_id=?", (r["agent_id"],))
        audit("system", "agent_heartbeat_timeout", r["agent_id"], {"cutoff": cutoff})
    return len(rows)
