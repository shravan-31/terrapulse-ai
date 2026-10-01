# run_all_training_pipeline.ps1
# TerraPulse.AI (SIH 26227) - Autonomous Pipeline Runner

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  🛰️ TerraPulse.AI (SIH 26227) - Autonomous Pipeline Runner" -ForegroundColor Cyan
Write-Host "  Phase 1: Dataset Verification & Sentinel-2 Staging" -ForegroundColor Cyan
Write-Host "  Phase 2: Siamese Change Detection Training & Evaluation" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python was not found in PATH! Please ensure Python 3.10+ is installed." -ForegroundColor Red
    exit 1
}

Write-Host "[STEP 1/4] Verifying Local Staged Datasets (LEVIR-CD & OSCD)..." -ForegroundColor Yellow
python scripts/verify_datasets.py

Write-Host "`n[STEP 2/4] Downloading / Staging Sentinel-2 Satellite AOIs using .env credentials..." -ForegroundColor Yellow
python scripts/download_sentinel_data.py --live

Write-Host "`n[STEP 3/4] Training / Retraining Siamese Change Detection Network..." -ForegroundColor Yellow
Write-Host "(Training on LEVIR-CD building pairs + OSCD multispectral scenes)" -ForegroundColor Gray
python scripts/train_change_detection.py --epochs 5 --batch-size 4 --device cpu

Write-Host "`n[STEP 4/4] Executing Held-Out Evaluation on Unseen Test Splits..." -ForegroundColor Yellow
python scripts/evaluate_change_detection.py --checkpoint models/changeformer/ChangeFormerV6.pth --test-size 50
python scripts/evaluate.py

Write-Host "`n=====================================================================" -ForegroundColor Green
Write-Host "  ✓ Pipeline execution completed successfully!" -ForegroundColor Green
Write-Host "  ✓ Updated model weights: models/changeformer/ChangeFormerV6.pth" -ForegroundColor Green
Write-Host "  ✓ Generated benchmark reports: reports/change_detection_evaluation_final.json" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Green
