# update_github_and_deploy.ps1
# TerraPulse AI - Push to GitHub & Live Vercel Deploy

Set-Location $PSScriptRoot

Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "  🛰️ TerraPulse AI (SIH 26227) - Push to GitHub & Live Vercel Deploy" -ForegroundColor Cyan
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[STEP 1/3] Staging updated codebase files..." -ForegroundColor Yellow
git add .
git status --short

Write-Host "`n[STEP 2/3] Committing updates with SIH 26227 verified trained model..." -ForegroundColor Yellow
git commit -m "feat(siamese-cd): integrate trained ChangeFormerV6 model, live model metrics card, and SIH 26227 semantic queries"

Write-Host "`n[STEP 3/3] Pushing to GitHub (origin main)..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=========================================================================" -ForegroundColor Green
    Write-Host "  ✓ Code pushed to GitHub successfully!" -ForegroundColor Green
    Write-Host "  ✓ Automatic Vercel deployment triggered for branch 'main'" -ForegroundColor Green
    Write-Host "  🌐 Live Deployment URL: https://terrapulse-ai-gules.vercel.app/" -ForegroundColor Green
    Write-Host "=========================================================================" -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] Git push failed. Please verify your connection or credentials." -ForegroundColor Red
}
