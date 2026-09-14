@echo off
REM 一键启动 NATS Server + Agent-Rotary-Station（P0 通信层）
REM 首次使用请先运行：python -m pip install -r requirements.txt
cd /d "%~dp0"

set NATS_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Packages\NATSAuthors.NATSServer_Microsoft.Winget.Source_8wekyb3d8bbwe\nats-server-v2.14.5-windows-amd64\nats-server.exe

if not exist "%NATS_EXE%" (
    echo [ERROR] 找不到 nats-server.exe，请先执行：
    echo   winget install NATSAuthors.NATSServer --accept-source-agreements --accept-package-agreements
    pause
    exit /b 1
)

echo [1/2] 启动 NATS Server (127.0.0.1:4222)...
start "NATS" /min "%NATS_EXE%" -p 4222

timeout /t 2 /nobreak >nul

echo [2/2] 启动 Agent-Rotary-Station (127.0.0.1:8000)...
set ARS_NATS_ENABLED=1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
