@echo off
setlocal
cd /d "%~dp0"
if not exist ".web-venv\Scripts\python.exe" (
    echo Run Setup_Server.bat first.
    pause
    exit /b 1
)
".web-venv\Scripts\python.exe" server.py
pause
