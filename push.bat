@echo off
setlocal

cd /d "%~dp0"

if not exist ".git" (
    echo No git repo found. Run: git init
    echo Then set remote: git remote add origin ^<url^>
    exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo No "origin" remote set. Run: git remote add origin ^<url^>
    exit /b 1
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set BRANCH=%%b

git add -A

git diff --cached --quiet
if errorlevel 1 (
    for /f "delims=" %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set STAMP=%%d
    git commit -m "update %STAMP%"
) else (
    echo Nothing to commit.
)

git push origin %BRANCH%

endlocal
