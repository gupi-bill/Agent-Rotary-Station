@echo off
REM Agent-Rotary-Station 一键启动（双击即可）
cd /d "%~dp0"

setlocal

REM ---- 找 Python：优先项目 venv，其次 py -3，最后 PATH ----
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
    echo.
    echo   [x] 没找到 Python。请安装 Python 3.10+ 并勾选 "Add to PATH"。
    echo       https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM ---- 首次运行装依赖 ----
"%PY%" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo   首次运行，正在装依赖...（需要几分钟）
    "%PY%" -m pip install -q -r requirements.txt
    if errorlevel 1 (
        echo   [x] 依赖安装失败。请手动执行： %PY% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo   Agent-Rotary-Station  -^>  http://127.0.0.1:8000
echo   关掉这个黑窗口即停止。
echo.
%PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
