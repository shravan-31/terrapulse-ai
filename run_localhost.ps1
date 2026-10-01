# TerraPulse AI - Local Host Launcher (PowerShell)
param(
    [ValidateSet("frontend", "backend", "both")]
    [string]$Target = "frontend"
)

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "        TERRAPULSE AI - LOCALHOST RUNNER ($Target)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

if ($Target -eq "frontend") {
    Write-Host "Starting Frontend at http://localhost:5173..." -ForegroundColor Green
    Set-Location (Join-Path $rootDir "frontend")
    npm run dev
} elseif ($Target -eq "backend") {
    Write-Host "Starting Backend API at http://localhost:8000..." -ForegroundColor Green
    Set-Location (Join-Path $rootDir "backend")
    if (Test-Path "venv\Scripts\Activate.ps1") {
        & "venv\Scripts\Activate.ps1"
    } elseif (Test-Path ".venv\Scripts\Activate.ps1") {
        & ".venv\Scripts\Activate.ps1"
    }
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} elseif ($Target -eq "both") {
    Write-Host "Launching Backend API in separate window..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\backend'; if (Test-Path 'venv\Scripts\Activate.ps1') { . 'venv\Scripts\Activate.ps1' }; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    
    Write-Host "Starting Frontend at http://localhost:5173..." -ForegroundColor Green
    Set-Location (Join-Path $rootDir "frontend")
    npm run dev
}
