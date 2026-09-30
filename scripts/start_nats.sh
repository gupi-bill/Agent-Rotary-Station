#!/usr/bin/env bash
# 一键启动 NATS Server + Agent-Rotary-Station（macOS / Linux）
#
# NATS 是 P0 通信层，必需。没有它 agents 之间无法通信。
set -e
cd "$(dirname "$0")"

NATS_PORT="${NATS_PORT:-4222}"
HOST="${ARS_HOST:-127.0.0.1}"
PORT="${ARS_PORT:-8000}"

# ---- 找 nats-server ----
NATS=""
for c in nats-server nats; do
  if command -v "$c" >/dev/null 2>&1; then NATS="$c"; break; fi
done

if [ -z "$NATS" ]; then
  echo "  [x] 没找到 nats-server。"
  echo
  echo "  安装："
  echo "    Debian/Ubuntu: sudo apt install nats-server"
  echo "    macOS:         brew install nats-server"
  echo "    或从 https://github.com/nats-io/nats-server/releases 下载"
  echo
  echo "  （不装也能跑：应用会退化成单进程模式，只是 agents 之间无法通信）"
  echo
  read -r -p "  按回车继续（仅启动 Station，不带 NATS）..." _
else
  echo "  [1/2] 启动 NATS Server (127.0.0.1:$NATS_PORT)..."
  "$NATS" -p "$NATS_PORT" &
  NATS_PID=$!
  sleep 2
fi

# ---- 找 Python ----
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then PY="venv/bin/python"; fi

if [ -z "$PY" ]; then
  echo "  [x] 没找到 Python。"
  echo "  Debian/Ubuntu: sudo apt install python3 python3-venv"
  exit 1
fi

if ! "$PY" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "  首次运行，正在建虚拟环境并装依赖..."
  [ -d ".venv" ] || "$PY" -m venv .venv
  ./.venv/bin/python -m pip install -q --upgrade pip
  ./.venv/bin/python -m pip install -q -r requirements.txt
  PY=".venv/bin/python"
fi

cleanup() {
  [ -n "${NATS_PID:-}" ] && kill "$NATS_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "  [2/2] 启动 Agent-Rotary-station → http://$HOST:$PORT"
echo "  （Ctrl+C 同时停止两者）"
echo
export ARS_NATS_ENABLED=1
exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
