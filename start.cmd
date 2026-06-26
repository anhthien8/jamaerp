@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title JAMA HOME CRM - Starting...

echo.
echo  =============================================
echo    JAMA HOME CRM - ERP + CRM Interior Design
echo    Dang khoi dong dich vu...
echo  =============================================
echo.

REM ── Step 1: Kill existing processes on ports 3001 and 8000 ──
echo  Dang dung cac process cu tren port 3001 va 8000...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3001" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo  [OK] Da dung cac process cu.
echo.

REM ── Step 2: Start Backend (FastAPI) ──
echo  Khoi dong Backend (FastAPI - port 8000)...
start "JAMA Backend" cmd /k "cd /d H:\Hermes\jama-crm\backend && set PYTHONIOENCODING=utf-8 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo  [OK] Backend da khoi dong.
echo.

REM ── Step 3: Wait for backend to start ──
echo  Dang cho Backend khoi dong (5 giay)...
timeout /t 5 /nobreak >nul
echo  [OK] Da cho xong.
echo.

REM ── Step 4: Start Frontend (Next.js) ──
echo  Khoi dong Frontend (Next.js - port 3001)...
echo  [?] Chon che do: (1) Development hot-reload  (2) Production build
echo.
set /p "FRONTEND_MODE= Nhap so (1 hoac 2, mac dinh 1): "

if "%FRONTEND_MODE%"=="2" (
    start "JAMA Frontend" cmd /k "cd /d H:\Hermes\jama-crm\frontend && npx next start -p 3001"
    echo  [OK] Frontend (Production) da khoi dong.
) else (
    start "JAMA Frontend" cmd /k "cd /d H:\Hermes\jama-crm\frontend && npm run dev"
    echo  [OK] Frontend (Development) da khoi dong.
)
echo.

REM ── Step 5: Open browser ──
echo  Dang mo trinh duyet...
timeout /t 3 /nobreak >nul
start http://localhost:3001

echo.
echo  =============================================
echo    TAT CA DICH VU DA KHOI DONG THANH CONG!
echo  =============================================
echo.
echo    Frontend : http://localhost:3001
echo    Backend  : http://localhost:8000
echo    API Docs : http://localhost:8000/docs
echo  =============================================
echo.
echo    Tai khoan Demo:
echo    Admin       : admin@jamahome.vn / admin123
echo    Giam doc    : ceo@jamahome.vn / ceo123
echo    Leader      : leader@jamahome.vn / leader123
echo    Sales       : sales@jamahome.vn / sales123
echo    Ke toan     : accountant@jamahome.vn / account123
echo  =============================================
echo.
echo    Nhan phim bat ky de dong cua so nay...
pause >nul
