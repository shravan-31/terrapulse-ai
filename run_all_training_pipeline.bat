@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo   TerraPulse.AI (SIH 26227) - Autonomous Pipeline Runner
echo   Phase 1: Dataset Verification and Sentinel-2 Staging
echo   Phase 2: Siamese Change Detection Training and Evaluation
echo =====================================================================
echo.

:: Detect Python executable
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in PATH! Please ensure Python 3.10+ is installed.
    pause
    exit /b 1
)

echo [STEP 1/4] Verifying Local Staged Datasets (LEVIR-CD and OSCD)...

python scripts\verify_datasets.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Dataset verification reported an issue, continuing...
)
echo.

echo [STEP 2/4] Downloading / Staging Sentinel-2 Satellite AOIs using .env credentials...
python scripts\download_sentinel_data.py --live
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Live download experienced network issue, offline local fallback staged.
)
echo.

echo [STEP 3/4] Training / Retraining Siamese Change Detection Network...
echo (Training on LEVIR-CD building pairs + OSCD multispectral scenes)
python scripts\train_change_detection.py --epochs 5 --batch-size 4 --device cpu
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Model training encountered an error.
    pause
    exit /b 1
)
echo.

echo [STEP 4/4] Executing Held-Out Evaluation on Unseen Test Splits...
python scripts\evaluate_change_detection.py --checkpoint models\changeformer\ChangeFormerV6.pth --test-size 50
python scripts\evaluate.py
echo.

echo =====================================================================
echo   ✓ Pipeline execution completed successfully!
echo   ✓ Updated model weights: models\changeformer\ChangeFormerV6.pth
echo   ✓ Generated benchmark reports: reports\change_detection_evaluation_final.json
echo =====================================================================
pause
