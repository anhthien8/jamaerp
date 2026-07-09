@echo off
chcp 65001 >nul 2>&1
title JAMA HOME CRM - Demo Launcher

echo.
echo  =============================================
echo    JAMA HOME CRM - Khoi dong che do Demo
echo  =============================================
echo.

REM ── Dung process cu tren port 8000 va 3001 ──
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3001" ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1

REM ── Backend (FastAPI - port 8000) ──
echo  Khoi dong Backend...
start "JAMA Backend" cmd /k "cd /d %~dp0backend && set PYTHONIOENCODING=utf-8 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM ── Cho backend khoi dong ──
timeout /t 6 /nobreak >nul

REM ── Worker (tu dong hoa + backup) ──
echo  Khoi dong Worker...
start "JAMA Worker" cmd /k "cd /d %~dp0backend && python -m app.worker"

REM ── Frontend (Next.js dev - port 3001) ──
echo  Khoi dong Frontend...
start "JAMA Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

REM ── Cho frontend build ──
echo  Cho Frontend build (20 giay)...
timeout /t 20 /nobreak >nul

REM ── Mo trinh duyet ──
start http://localhost:3001

echo.
echo  =============================================
echo    DA KHOI DONG! Mo http://localhost:3001
echo    Backend:  http://localhost:8000/health
echo    API Docs: http://localhost:8000/docs
echo.
echo    Dang nhap: admin@jamahome.vn / admin123
echo  =============================================
echo.
echo  Dong cua so nay khong sao (cac dich vu chay o cua so rieng).
timeout /t 8 /nobreak >nul
