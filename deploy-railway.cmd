@echo off
REM ====================================================
REM  JAMA CRM — Deploy to Railway (run this in your terminal)
REM ====================================================
echo.
echo ========================================
echo   JAMA CRM — Railway Deploy Script
echo ========================================
echo.

REM Step 1: Login
echo [1/4] Dang nhap Railway...
railway login
if errorlevel 1 (
    echo [FAIL] Login that bai. Vui long thu lai.
    pause
    exit /b 1
)
echo [OK] Da login thanh cong!
echo.

REM Step 2: List projects
echo [2/4] Danh sach project hien co:
railway list
echo.
echo Neu chua co project, script se tao moi...
echo.

REM Step 3: Link or create project
echo [3/4] Link project...
railway link
if errorlevel 1 (
    echo Tao project moi...
    railway init
)
echo.

REM Step 4: Deploy backend
echo [4/4] Deploy backend len Railway...
cd /d H:\Hermes\jama-crm
railway up
if errorlevel 1 (
    echo [FAIL] Deploy that bai!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   DEPLOY THANH CONG!
echo ========================================
echo.
echo Kiem tra: railway status
echo Logs:    railway logs
echo Domain:  railway domain
echo.
echo Nho dat bien moi truong:
echo   JWT_SECRET_KEY (bat buoc, ^>=32 ky tu)
echo   APP_ENV=production
echo   CORS_ORIGINS=domain-frontend
echo.
pause
