@echo off
REM Agent-Rotary-Station 一键启动（双击即可）
cd /d "%~dp0"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
