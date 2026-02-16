@echo off
setlocal enabledelayedexpansion
title FilePortal - FORCE UPDATE Deploy
color 0C

echo ==========================================
echo   FORCE DEPLOY - LATEST CHANGES ONLY
echo ==========================================
echo.

:: Ensure we are in the project folder
cd /d "%~dp0"

:: AGGRESSIVE: Remove all Git cache
echo [0/5] Clearing Git cache...
git rm -r --cached . >nul 2>&1

:: 1. SYNC REMOTE URL
echo [1/5] Syncing remote...
git remote set-url origin https://github.com/myexcelweb/fileportal.git >nul 2>&1

:: 2. DETECT BRANCH
for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i
if "%branch%"=="" (set branch=main)
echo Branch: %branch%

:: 3. ADD EVERYTHING (including previously ignored)
echo [2/5] Adding ALL files forcefully...
git add -A
git add --force .

:: 4. COMMIT with timestamp to ensure uniqueness
echo [3/5] Creating unique commit...
set timestamp=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set timestamp=%timestamp: =0%
git commit -m "FORCE UPDATE Real-Time %timestamp%" --allow-empty

:: 5. FORCE PUSH
echo [4/5] FORCE PUSHING to GitHub...
echo.
echo WARNING: This will overwrite remote with local changes!
echo Press Ctrl+C to cancel, or
pause

git push origin %branch% --force

:: 6. TRIGGER RENDER
if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo    FORCE PUSH COMPLETED
    echo ==========================================
    echo.
    echo [NEXT STEPS - CRITICAL!]
    echo.
    echo 1. Go to Render: https://dashboard.render.com
    echo 2. Select: fileportal-qpzs
    echo 3. Click: Manual Deploy (top right)
    echo 4. Select: Clear build cache and deploy
    echo 5. Update Start Command to:
    echo    gunicorn --worker-class eventlet -w 1 app:app
    echo.
    echo ==========================================
    echo This FORCES Render to use LATEST code!
    echo ==========================================
) else (
    echo.
    echo [ERROR] Force push failed!
    echo Try: git pull origin %branch% --rebase
    echo Then run this script again
)

echo.
echo ==========================================
pause
