@echo off
REM =========================================================================
REM TerraPulse AI - One-Click Asset Synchronization & JPG Export Script
REM Double-click to generate all JPG and PNG screenshots
REM =========================================================================

echo ==========================================================
echo  TerraPulse AI - Generating JPG and PNG Screenshots...
echo ==========================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_assets.ps1"

echo.
echo ==========================================================
echo  Process completed!
echo ==========================================================
pause
