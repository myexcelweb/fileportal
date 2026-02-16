@echo off
setlocal enabledelayedexpansion
title FilePortal - Auto Git Push and Deploy
color 0B

echo ==========================================
echo      FILEPORTAL - SECURE DEPLOYMENT
echo ==========================================
echo.

:: Ensure we are in the correct folder
cd /d "%~dp0"

:: Detect current branch
for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i
if "%branch%"=="" (set branch=main)

echo [INFO] Current Branch: %branch%
echo.

:: Step 1: Stage all changes
echo [1/4] Staging files...
git add .

:: Step 2: Commit the changes
echo [2/4] Committing changes...
:: We check if there are changes. If yes, we commit using a direct string to avoid empty variable errors.
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "FilePortal Update: %date% %time%"
) else (
    echo [SKIP] No new changes to commit.
)

:: Step 3: Pull latest changes from GitHub
echo.
echo [3/4] Pulling updates from GitHub...
:: Using --rebase to keep history clean
git pull origin %branch% --rebase

:: Step 4: Push to GitHub
echo.
echo [4/4] Pushing code to GitHub...
git push origin %branch%

:: Final Check
if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo      SUCCESS: CODE SYNCED SUCCESSFULLY
    echo ==========================================
    echo.
    echo [ACTION] Render is now building your update!
    echo [URL] Check: https://fileportal.onrender.com
    echo.
) else (
    echo.
    echo [ERROR] Push failed. 
    echo Please check for merge conflicts or internet issues.
)

echo ==========================================
pause