@echo off
echo ==========================================================
echo   TerraPulse AI - Pushing to GitHub (Batch Runner)
echo ==========================================================
git add .
git status --short
git commit -m "fix(investigation): resolve laptop view layout visibility with workspace switcher and display authentic satellite map in comparison viewer"
git push origin main
echo.
echo All changes pushed to GitHub successfully!
pause
