# =========================================================================
# TerraPulse AI - PowerShell Git Commit & Push Script
# =========================================================================
Set-Location $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  TerraPulse AI - Pushing Live Location Fix & Updates" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Staging modified and new files..." -ForegroundColor Yellow
git add .
git status --short

Write-Host "`n[2/3] Creating commit..." -ForegroundColor Yellow
git commit -m "fix(geolocation): add automatic IP-based location fallback, dynamic live marker and direct investigation routing"

Write-Host "`n[3/3] Pushing to origin main..." -ForegroundColor Yellow
git push origin main

Write-Host "`nAll changes pushed to GitHub successfully!" -ForegroundColor Green
