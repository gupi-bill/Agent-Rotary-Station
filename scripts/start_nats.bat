@echo off
REM 一键启动 NATS Server + Agent-Rotary-Station（P0 通信层）
REM 首次使用请先运行：python -m pip install -r requirements.txt
cd /d "%~dp0"

setlocal

REM ---- 找 nats-server：优先 PATH，其次常见的 winget 安装位置 ----
set "NATS_EXE="
where nats-server.exe >nul 2>nul && set "NATS_EXE=nats-server.exe"

if not defined NATS_EXE (
    for /f "delims=" %%i in ('where /r "%LOCALAPPDATA%\Microsoft\WinGet\Packages" nats-server.exe 2^>nul') do (
        if not defined NATS_EXE set "NATS_EXE=%%i"
    )
)

if not defined NATS_EXE if exist "C:\Program Files\nats\nats-server.exe" set "NATS_EXE=C:\Program Files\nats\nats-server.exe"

if not defined NATS_EXE (
    echo.
    echo   [x] 没找到 nats-server.exe。
    echo.
    echo   安装：winget install NATSAuthors.NATSServer
    echo         或从 https://github.com/nats-io/nats-server/releases 下载
    echo.
    echo   （不装也能跑：应用会退化成单进程模式，只是 agents 之间无法通信）
    echo.
    set /p "=按回车继续（仅启动 Station，不带 NATS）... "
    echo.
) else (
    echo   [1/2] 启动 NATS Server ^(127.0.0.1:4222^)...
    echo         可执行文件：%NATS_EXE%
    start "NATS" /min "%NATS_EXE%" -p 4222
    timeout /t 2 /nobreak >nul
)

REM ---- 找 Python ----
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
    echo   [x] 没找到 Python。请安装 Python 3.10+ 并勾选 "Add to PATH"。
    pause
    exit /b 1
)

"%PY%" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo   首次运行，正在装依赖...
    "%PY%" -m pip install -q -r requirements.txt
)

echo   [2/2] 启动 Agent-Rotary-Station ^(http://127.0.0.1:8000^)...
echo         关掉这个黑窗口即停止。
echo.
set "ARS_NATS_ENABLED=1"
%PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
