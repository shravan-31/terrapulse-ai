# scripts/setup_windows.ps1
# Windows Development Setup & Offline Platform Initialization (Section 46)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " TerraPulse AI — Windows Environment Setup & Initialization" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
Set-Location $WorkspaceRoot

# 1. Check Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Error "Python was not found on PATH. Please install Python 3.10-3.13."
    exit 1
}
Write-Host "[OK] Python detected: $($PythonCmd.Source)" -ForegroundColor Green

# 2. Virtual Environment
$VenvPath = Join-Path $WorkspaceRoot "backend\venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "[INFO] Creating virtual environment at $VenvPath..." -ForegroundColor Yellow
    python -m venv $VenvPath
}
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Gray
    & $ActivateScript
}

# 3. Create required data folders
$Dirs = @(
    "data\raw",
    "data\processed",
    "data\tiles",
    "data\thumbnails",
    "data\masks",
    "data\embeddings",
    "data\indexes",
    "data\catalog\items",
    "data\reports",
    "data\demo",
    "config",
    "models\remoteclip",
    "models\changeformer"
)

foreach ($dir in $Dirs) {
    $full = Join-Path $WorkspaceRoot $dir
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
}
Write-Host "[OK] Required data and storage directories verified." -ForegroundColor Green

# 4. Check Environment & Dependencies
Write-Host "`n[INFO] Running environment diagnostics..." -ForegroundColor Cyan
python scripts\check_environment.py

# 5. Check Database & PostGIS
Write-Host "`n[INFO] Checking database connectivity..." -ForegroundColor Cyan
python scripts\check_database.py

# 6. Verify Offline AI Models
Write-Host "`n[INFO] Checking offline models..." -ForegroundColor Cyan
python scripts\setup_models.py

# 7. Initialize Demo Data & Index
Write-Host "`n[INFO] Initializing demo data and local FAISS vector index..." -ForegroundColor Cyan
python scripts\demo_setup.py

# 8. Run Offline Acceptance Verification
Write-Host "`n[INFO] Running offline acceptance test suite..." -ForegroundColor Cyan
python scripts\offline_validation.py

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host " SUCCESS: TerraPulse AI is ready for Windows and Offline Operations!" -ForegroundColor Green
Write-Host " Run backend : .\backend\venv\Scripts\activate; uvicorn app.main:app --port 8000 --reload" -ForegroundColor Gray
Write-Host " Run frontend: cd frontend; npm run dev" -ForegroundColor Gray
Write-Host "======================================================================" -ForegroundColor Green
