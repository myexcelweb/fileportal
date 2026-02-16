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

:: 1. VERIFY GIT INSTALLATION
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not in your PATH.
    pause
    exit /b
)

:: 2. SYNC REMOTE URL
:: This ensures your local folder points to the NEW fileportal repo
echo [1/6] Updating Repository Path...
git remote set-url origin https://github.com/myexcelweb/fileportal.git >nul 2>&1
if %errorlevel% neq 0 (
    git remote add origin https://github.com/myexcelweb/fileportal.git >nul 2>&1
)

:: 3. DETECT BRANCH
for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i
if "%branch%"=="" (set branch=main)
echo [INFO] Current Branch: %branch%

:: 4. STAGE AND COMMIT
echo [2/6] Staging files...
git add .

echo [3/6] Checking for changes...
git diff --cached --quiet
if %errorlevel% neq 0 (
    echo [INFO] Committing changes...
    git commit -m "FilePortal Update: %date% %time%"
) else (
    echo [SKIP] No new changes to commit.
)

:: 5. PULL REBASE
echo [4/6] Pulling latest updates from GitHub...
git pull origin %branch% --rebase
if %errorlevel% neq 0 (
    echo [ERROR] Failed to pull. You might have a conflict or no internet.
    pause
    exit /b
)

:: 6. THE PUSH & VERIFICATION
echo [5/6] Pushing code to GitHub...
git push origin %branch%

:: VERIFY SUCCESS
if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo    VERIFIED: PUSH COMPLETED SUCCESSFULLY
    echo ==========================================
    echo [6/6] Update confirmed on GitHub.
    echo.
    echo [ACTION] Render is now building your update!
    echo [URL] Check: https://fileportal.onrender.com
    echo.
) else (
    echo.
    echo ==========================================
    echo       CRITICAL ERROR: PUSH FAILED
    echo ==========================================
    echo [CHECK] 1. Is your internet working?
    echo [CHECK] 2. Does the repo 'fileportal' exist on GitHub?
    echo [CHECK] 3. Do you have permission to push?
    echo.
)

echo ==========================================
pause