@echo off
setlocal enabledelayedexpansion
title FilePortal - Auto Git Push and Deploy
color 0B

echo ==========================================
echo      FILEPORTAL - SECURE DEPLOYMENT
echo ==========================================
echo.

:: Ensure we are in the project folder
cd /d "%~dp0"

:: 1. SYNC REMOTE URL
git remote set-url origin https://github.com/myexcelweb/fileportal.git >nul 2>&1

:: 2. DETECT BRANCH
for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i
if "%branch%"=="" (set branch=main)

:: 3. STAGE AND COMMIT
echo [1/4] Staging files...
git add .

echo [2/4] Checking for changes...
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "FilePortal Update: %date% %time%"
) else (
    echo [SKIP] No new changes to commit.
)

:: 4. PULL (With error suppression for new repos)
echo [3/4] Checking for remote updates...
git pull origin %branch% --rebase >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Note: Remote branch not found or empty. Proceeding...
)

:: 5. THE PUSH
echo [4/4] Pushing code to GitHub...
:: Use -u to ensure the upstream link is solid
git push -u origin %branch%

:: VERIFY SUCCESS
if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo    VERIFIED: PUSH COMPLETED SUCCESSFULLY
    echo ==========================================
    echo.
    echo [ACTION] Render is now building your update!
    echo [URL] Check: https://fileportal.onrender.com
) else (
    echo.
    echo [ERROR] Push failed. Check your GitHub permissions or internet.
)

echo ==========================================
pause