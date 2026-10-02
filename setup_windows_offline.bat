@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo  TerraPulse AI — Windows Offline Setup and Verification
echo ======================================================================

cd /d "%~dp0"

:: 1. Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Please install Python 3.10-3.13.
    pause
    exit /b 1
)

:: 2. Activate Virtual Environment if present
if exist "backend\venv\Scripts\activate.bat" (
    echo [INFO] Activating backend virtual environment...
    call "backend\venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call "venv\Scripts\activate.bat"
)

:: 3. Create required data and storage directories
echo [INFO] Creating required data directories...
if not exist "data\raw" mkdir "data\raw"
if not exist "data\processed" mkdir "data\processed"
if not exist "data\tiles" mkdir "data\tiles"
if not exist "data\thumbnails" mkdir "data\thumbnails"
if not exist "data\masks" mkdir "data\masks"
if not exist "data\embeddings" mkdir "data\embeddings"
if not exist "data\indexes" mkdir "data\indexes"
if not exist "data\catalog\items" mkdir "data\catalog\items"
if not exist "reports" mkdir "reports"

:: 4. Generate Demo Dataset and Index
echo.
echo [INFO] Running demo dataset generation and local vector indexing...
python scripts\demo_setup.py
if %errorlevel% neq 0 (
    echo [WARN] Demo setup returned non-zero code. Checking files...
)

:: 5. Run Offline Acceptance Verification Suite
echo.
echo [INFO] Running offline acceptance test suite...
python scripts\verify_offline.py
if %errorlevel% neq 0 (
    echo [FAIL] Offline verification failed!
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo  SUCCESS: TerraPulse AI is completely configured for offline operation!
echo  To run the system:
echo    1. Backend:  cd backend ^& python -m uvicorn app.main:app --port 8000 --reload
echo    2. Frontend: cd frontend ^& npm run dev
echo ======================================================================
pause
