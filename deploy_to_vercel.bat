@echo off
REM =========================================================================
REM TerraPulse AI - Build & Deploy Directly to Vercel Production
REM =========================================================================
cd /d "%~dp0"

echo =========================================================================
echo   TerraPulse AI - Deploying Updates to Vercel Production
echo =========================================================================
echo.

echo [1/3] Building frontend with latest code...
cd frontend
call npm install
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b %errorlevel%
)
cd ..

echo.
echo [2/3] Checking Vercel login authentication...
echo If it asks to login, please choose "Continue with GitHub" or your email in browser.
call npx vercel whoami
if %errorlevel% neq 0 (
    echo.
    echo Please log in to your Vercel account:
    call npx vercel login
)

echo.
echo [3/3] Deploying build to Vercel Production...
call npx vercel --prod

echo.
echo =========================================================================
echo   Deployment Process Finished!
echo   Open: https://terrapulse-ai-gules.vercel.app/
echo =========================================================================
pause
