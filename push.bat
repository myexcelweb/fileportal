@echo off
title File Transfer App - Auto Git Push
color 0A

echo ==========================================
echo     FILE TRANSFER APP - AUTO GIT PUSH
echo ==========================================
echo.

:: Go to script directory
cd /d "%~dp0"

echo Current Folder:
cd
echo.

:: Check if git exists
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Git is not installed.
    pause
    exit /b
)

:: Check if git repo
if not exist ".git" (
    echo ERROR: This folder is not a git repository.
    pause
    exit /b
)

:: Detect branch
for /f "tokens=*" %%i in ('git branch --show-current') do set branch=%%i
if "%branch%"=="" (
    set branch=main
)

echo Current branch: %branch%
echo.

:: Pull latest changes first (avoid conflicts)
echo Pulling latest changes...
git pull origin %branch%
echo.

:: Add all changes
git add .

:: Check if there are changes to commit
git diff --cached --quiet
if %errorlevel%==0 (
    echo No changes to commit.
    echo.
    echo ==========================================
    echo         NOTHING TO PUSH
    echo ==========================================
    pause
    exit /b
)

:: Auto commit message with date & time
set msg=Auto Update %date% %time%

echo Committing with message:
echo %msg%
echo.

git commit -m "%msg%"

echo.
echo Pushing to GitHub...
git push -u origin %branch%

echo.
echo ==========================================
echo      PUSH COMPLETED SUCCESSFULLY
echo ==========================================
pause
