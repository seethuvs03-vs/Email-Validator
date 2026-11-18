@echo off
setlocal
cd /d "%~dp0"
python -m venv .web-venv
if errorlevel 1 goto failed
".web-venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".web-venv\Scripts\python.exe" setup_server.py
if errorlevel 1 goto failed
echo.
echo Setup complete. Run Start_Server.bat, then open http://localhost:8080
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.10 or newer and check the error above.
pause
exit /b 1
