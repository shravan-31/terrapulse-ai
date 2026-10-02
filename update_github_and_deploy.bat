@echo off
setlocal enabledelayedexpansion

echo =========================================================================
echo   🛰️ TerraPulse AI (SIH 26227) - Push to GitHub & Live Vercel Deploy
echo =========================================================================
echo.

cd /d "%~dp0"

echo [STEP 1/3] Staging all updated codebase files...
git add .
git status --short
echo.

echo [STEP 2/3] Committing updates with full offline satellite intelligence platform...
git commit -m "feat(offline-platform): complete offline satellite intelligence platform with model abstraction, classical/deep change detection, geospatial raster engine, local STAC catalog, ReportLab PDF reports, and Ingest UI"
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] No new changes to commit or commit succeeded.
)
echo.

echo [STEP 3/3] Pushing to GitHub (origin main)...
git push origin main
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git push failed. Please check your GitHub remote or network connection.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =========================================================================
echo   ✓ Code pushed to GitHub successfully!
echo   ✓ Automatic Vercel deployment triggered for branch 'main'
echo   🌐 Live Deployment URL: https://terrapulse-ai-gules.vercel.app/
echo =========================================================================
echo.
echo Would you also like to run direct CLI production build to Vercel?
set /p deployChoice="Deploy directly now via Vercel CLI? [y/N]: "
if /i "%deployChoice%"=="y" (
    echo Building and deploying directly...
    call deploy_to_vercel.bat
)

pause
