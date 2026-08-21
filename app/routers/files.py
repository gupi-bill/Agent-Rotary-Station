"""文件访问：供 BlueDeer-Console IDE 工作台编辑底座项目文件。

安全设计：
- 工作区根 = 本服务项目根（Agent-Rotary-Station/），所有路径必须解析在根内；
- 黑名单目录（.venv/data/.git/__pycache__/node_modules 等）一律拒绝；
- 路径经 realpath 规范化，防 ../ 穿越。
"""
from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter(prefix="/files", tags=["files"])

WORKSPACE = Path(__file__).resolve().parent.parent.parent  # .../Agent-Rotary-Station
BLOCKED_PARTS = {".venv", "venv", ".git", "__pycache__", "node_modules",
                 ".pytest_cache", ".mypy_cache", ".ruff_cache", ".coverage",
                 "data", "logs", "backups", "hermes"}
MAX_SIZE = 2 * 1024 * 1024  # 2MB


def _resolve(rel: str) -> Path:
    """相对路径 → 绝对路径，校验在工作区内且不在黑名单。"""
    rel = (rel or "").replace("\\", "/").lstrip("/")
    p = (WORKSPACE / rel).resolve()
    try:
        p.relative_to(WORKSPACE)
    except ValueError:
        raise HTTPException(status_code=403, detail="path outside workspace")
    for part in p.parts:
        if part in BLOCKED_PARTS:
            raise HTTPException(status_code=403, detail=f"blocked directory: {part}")
    return p


def _lang(name: str) -> str:
    ext = Path(name).suffix.lower()
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
        ".json": "json", ".md": "markdown", ".html": "html", ".css": "css",
        ".yaml": "yaml", ".yml": "yaml", ".toml": "ini", ".txt": "plaintext",
        ".sh": "shell", ".bat": "bat", ".mjs": "javascript", ".cjs": "javascript",
        ".sql": "sql", ".vue": "html", ".xml": "xml",
    }.get(ext, "plaintext")


@router.get("/list")
def list_files(path: str = ""):
    """列目录：path 为空=工作区根。返回子项（目录在前）。"""
    p = _resolve(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="path not found")
    if p.is_file():
        return {"ok": True, "path": str(p.relative_to(WORKSPACE)).replace("\\", "/"),
                "file": True, "entries": []}
    entries = []
    try:
        for child in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
            if child.name.startswith(".") and child.name not in (".gitignore",):
                continue
            try:
                st = child.stat()
            except Exception:
                continue
            rel = str(child.relative_to(WORKSPACE)).replace("\\", "/")
            if any(part in BLOCKED_PARTS for part in child.parts):
                continue
            entries.append({
                "name": child.name, "path": rel, "is_dir": child.is_dir(),
                "size": st.st_size if child.is_file() else 0,
                "mtime": int(st.st_mtime),
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "path": str(p.relative_to(WORKSPACE)).replace("\\", "/"),
            "file": False, "entries": entries}


@router.get("/content")
def read_file(path: str):
    """读文件内容（文本，限 2MB）。"""
    p = _resolve(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="not a file")
    size = p.stat().st_size
    if size > MAX_SIZE:
        raise HTTPException(status_code=413, detail="file too large")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"read error: {e}")
    return {"ok": True, "path": str(p.relative_to(WORKSPACE)).replace("\\", "/"),
            "content": content, "size": size,
            "language": _lang(p.name), "name": p.name}


@router.post("/content")
def write_file(body: dict):
    """写文件（真实落盘，覆盖）。"""
    rel = body.get("path", "")
    content = body.get("content", "")
    p = _resolve(rel)
    if p.is_dir():
        raise HTTPException(status_code=400, detail="is a directory")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"write error: {e}")
    db.audit("human", "file_write", str(p.relative_to(WORKSPACE)))
    return {"ok": True, "path": str(p.relative_to(WORKSPACE)).replace("\\", "/"),
            "size": p.stat().st_size, "mtime": int(time.time())}


@router.post("/create")
def create_node(body: dict):
    """新建文件或目录。"""
    rel = body.get("path", "")
    is_dir = bool(body.get("is_dir", False))
    p = _resolve(rel)
    if p.exists():
        raise HTTPException(status_code=400, detail="already exists")
    try:
        if is_dir:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    db.audit("human", "file_create", str(p.relative_to(WORKSPACE)), {"is_dir": is_dir})
    return {"ok": True, "path": str(p.relative_to(WORKSPACE)).replace("\\", "/")}


@router.post("/delete")
def delete_node(body: dict):
    """删除文件/空目录（限工作区内）。"""
    rel = body.get("path", "")
    p = _resolve(rel)
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    try:
        if p.is_dir():
            p.rmdir()  # 仅空目录
        else:
            p.unlink()
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"delete error: {e}")
    db.audit("human", "file_delete", str(p.relative_to(WORKSPACE)))
    return {"ok": True}
