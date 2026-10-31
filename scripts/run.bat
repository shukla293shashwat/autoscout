@echo off
REM One-command run: starts backend (8000) + frontend (5173) together.
REM Usage: scripts\run.bat   (Ctrl+C stops both)

setlocal
set ROOT=%~dp0..

echo Starting AutoScout backend on :8000 ...
start "AutoScout backend" cmd /k "cd /d "%ROOT%\backend" && python -m uvicorn app.main:app --reload --port 8000"

echo Starting AutoScout frontend on :5173 ...
start "AutoScout frontend" cmd /k "cd /d "%ROOT%\frontend" && npm run dev"

echo.
echo Backend  -> http://localhost:8000/health
echo Frontend -> http://localhost:5173
echo Close the two "AutoScout" windows to stop.
exit /b 0
