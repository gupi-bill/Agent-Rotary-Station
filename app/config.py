"""集中配置：全部可调项都走环境变量，给企业化留口子。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("ARS_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("ARS_DB_PATH", DATA_DIR / "station.db"))

# 工作站自身安全
STATION_TOKEN = os.getenv("ARS_STATION_TOKEN", "")  # 生产必填；空=开发模式
EMERGENCY_BLOCK = os.getenv("ARS_EMERGENCY_BLOCK", "0") == "1"  # 最高紧急刹车

# 转发配置（底座不推理，只转发）
HTTP_TIMEOUT = float(os.getenv("ARS_HTTP_TIMEOUT", "30"))

# v0.2 P1 工具离线排队
TOOL_QUEUE_MAX_RETRIES = int(os.getenv("ARS_TOOL_QUEUE_MAX_RETRIES", "5"))
TOOL_QUEUE_EXPIRE_SECONDS = float(os.getenv("ARS_TOOL_QUEUE_EXPIRE_SECONDS", "300"))
TOOL_QUEUE_RETRY_INTERVAL = float(os.getenv("ARS_TOOL_QUEUE_RETRY_INTERVAL", "5"))

# v0.2 P1 Agent 心跳超时（秒）
AGENT_HEARTBEAT_TIMEOUT = float(os.getenv("ARS_AGENT_HEARTBEAT_TIMEOUT", "60"))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
