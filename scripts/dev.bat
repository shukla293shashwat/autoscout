@echo off
REM AutoScout developer scripts (Windows)

IF "%1"=="backend-dev"  goto BACKEND
IF "%1"=="frontend-dev" goto FRONTEND
IF "%1"=="test"         goto TEST
echo Usage: scripts\dev.bat [backend-dev^|frontend-dev^|test]
exit /b 1

:BACKEND
cd /d "%~dp0..\backend"
python -m uvicorn app.main:app --reload --port 8000
exit /b %errorlevel%

:FRONTEND
cd /d "%~dp0..\frontend"
npm run dev
exit /b %errorlevel%

:TEST
cd /d "%~dp0..\backend"
python -m pytest -q
exit /b %errorlevel%
