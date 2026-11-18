@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: creating the application environment...
    python -m venv .venv
    if errorlevel 1 goto failed
)
if not exist ".venv\ready.txt" (
    echo Installing dependencies. An internet connection is needed for first-time setup.
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
    echo ready>".venv\ready.txt"
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Could not start Email Cleaner. Check the error above.
echo Python 3.10 or newer must be installed with the Python command available.
pause
exit /b 1
