@echo off
title File Transfer App - Git Push

echo ==========================================
echo        FILE TRANSFER APP - GIT PUSH
echo ==========================================
echo.

:: Make sure we are in correct folder
cd /d %~dp0

echo Current Folder:
cd
echo.

:: Check git
git status
echo.

:: Add all changes
echo Adding files...
git add .

echo.
set /p msg=Enter commit message: 

echo.
echo Committing...
git commit -m "%msg%"

echo.
echo Pushing to GitHub...
git push -u origin main

echo.
echo ==========================================
echo             PUSH COMPLETED
echo ==========================================
pause
