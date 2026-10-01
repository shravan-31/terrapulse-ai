@echo off
REM =========================================================================
REM TerraPulse AI - Git Add, Commit and Push to GitHub
REM =========================================================================
cd /d "%~dp0"

echo =========================================================================
echo   TerraPulse AI - Pushing Live Location Fix & Updates to GitHub
echo =========================================================================
echo.

echo [1/3] Staging changes...
git add .
git status --short

echo.
echo [2/3] Committing changes...
git commit -m "fix(geolocation): add automatic IP-based location fallback, dynamic live marker and direct investigation routing"

echo.
echo [3/3] Pushing to GitHub...
git push origin main

echo.
echo =========================================================================
echo   Git Push Process Completed Successfully!
echo =========================================================================
pause
