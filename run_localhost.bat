@echo off
title TerraPulse AI - Local Host Launcher
cls
echo ========================================================
echo         TERRAPULSE AI - LOCALHOST RUNNER
echo ========================================================
echo.
echo Select an option to start:
echo [1] Start FRONTEND only (http://localhost:5173)
echo [2] Start BACKEND API only (http://localhost:8000)
echo [3] Setup Backend Server Dependencies & Start Backend
echo [4] Start BOTH (Frontend + Backend in separate windows)
echo [5] Exit
echo.

set /p choice="Enter choice [1-5] (default is 1): "
if "%choice%"=="" set choice=1

if "%choice%"=="1" goto start_frontend
if "%choice%"=="2" goto start_backend
if "%choice%"=="3" goto setup_backend
if "%choice%"=="4" goto start_both
if "%choice%"=="5" goto end

:start_frontend
echo.
echo Launching TerraPulse AI Frontend on http://localhost:5173 ...
cd /d "%~dp0frontend"
npm run dev
goto end

:setup_backend
echo.
echo ========================================================
echo Setting up Python Virtual Environment in backend\venv ...
echo ========================================================
cd /d "%~dp0backend"
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if errorlevel 1 py -m venv venv
)
call venv\Scripts\activate.bat
echo Installing server dependencies (FastAPI, SQLAlchemy, Uvicorn, etc.)...
pip install -r requirements-server.txt
echo.
echo Setup completed! Starting backend server...
goto run_backend_server

:start_backend
cd /d "%~dp0backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    goto run_backend_server
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    goto run_backend_server
) else (
    echo.
    echo [WARNING] No active virtual environment found.
    echo Running setup now...
    goto setup_backend
)

:run_backend_server
echo.
echo Launching TerraPulse AI Backend API on http://localhost:8000 ...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
if errorlevel 1 (
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
)
goto end

:start_both
echo.
echo Starting TerraPulse AI Backend in a new window...
start "TerraPulse Backend API (Port 8000)" cmd /k "cd /d %~dp0backend && (if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat) && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting TerraPulse AI Frontend on http://localhost:5173...
cd /d "%~dp0frontend"
npm run dev
goto end

:end
