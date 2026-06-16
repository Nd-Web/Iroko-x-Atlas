@echo off
title Iroko AI

echo Starting Iroko AI...
echo.

cd /d "%~dp0"

:: ── Backend ──────────────────────────────────────────────────────────────────
start "Iroko Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate.bat && uvicorn main:app --reload --port 8000"

:: Give the backend a moment to bind before the frontend starts
timeout /t 3 /nobreak >nul

:: ── Frontend ─────────────────────────────────────────────────────────────────
start "Iroko Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Both servers are starting in separate windows.
echo   Backend:  http://localhost:8000
echo   API docs: http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo.
echo Close those two windows to stop the servers.
pause
