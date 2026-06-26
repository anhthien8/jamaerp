@echo off
title JAMA HOME CRM - Dev Environment

echo ========================================
echo   JAMA HOME CRM - Starting Services...
echo ========================================

REM --- Start Backend (FastAPI) ---
echo [1/3] Starting Backend (port 8000)...
start "JAMA Backend" cmd /k "cd /d H:\Hermes\jama-crm\backend && set PYTHONIOENCODING=utf-8 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM --- Start Frontend (Next.js) ---
echo [2/3] Starting Frontend (port 3001)...
start "JAMA Frontend" cmd /k "cd /d H:\Hermes\jama-crm\frontend && npx next start -p 3001"

REM --- Wait for servers ---
echo [3/3] Waiting for servers...
timeout /t 5 /nobreak >nul

REM --- Open Browser ---
echo Opening JAMA HOME CRM in browser...
start http://localhost:3001

echo.
echo ========================================
echo   All services started!
echo   Frontend: http://localhost:3001
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Press any key to close this window...
pause >nul
