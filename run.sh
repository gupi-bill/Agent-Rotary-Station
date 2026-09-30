#!/usr/bin/env bash
# Agent-Rotary-Station 一键启动（macOS / Linux）
set -e
cd "$(dirname "$0")"

HOST="${ARS_HOST:-127.0.0.1}"
PORT="${ARS_PORT:-8000}"

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
  echo "  Fedora:        sudo dnf install python3"
  echo "  macOS:         brew install python@3.12"
  exit 1
fi

# ---- 首次运行装依赖 ----
if ! "$PY" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "  首次运行，正在建虚拟环境并装依赖..."
  [ -d ".venv" ] || "$PY" -m venv .venv
  ./.venv/bin/python -m pip install -q --upgrade pip
  ./.venv/bin/python -m pip install -q -r requirements.txt
  PY=".venv/bin/python"
  echo "  依赖装好了。"
fi

echo "  Agent-Rotary-Station → http://$HOST:$PORT"
echo "  （Ctrl+C 停止）"
echo
exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
