@echo off
title File Verification Check
color 0E

echo ==========================================
echo   VERIFY LOCAL FILES
echo ==========================================
echo.

:: Check critical files exist
echo Checking files...
echo.

if exist "app.py" (
    echo [OK] app.py exists
    findstr /C:"flask_socketio" app.py >nul
    if %errorlevel% equ 0 (
        echo     [OK] Contains flask_socketio
    ) else (
        echo     [ERROR] Missing flask_socketio import!
    )
) else (
    echo [ERROR] app.py NOT FOUND!
)

echo.
if exist "templates\index.html" (
    echo [OK] templates\index.html exists
    findstr /C:"/create" templates\index.html >nul
    if %errorlevel% equ 0 (
        echo     [OK] Contains /create route
    ) else (
        echo     [ERROR] Still using old /create-room!
    )
) else (
    echo [ERROR] templates\index.html NOT FOUND!
)

echo.
if exist "templates\room.html" (
    echo [OK] templates\room.html exists
    findstr /C:"socket.io" templates\room.html >nul
    if %errorlevel% equ 0 (
        echo     [OK] Contains socket.io
    ) else (
        echo     [ERROR] Missing socket.io!
    )
) else (
    echo [ERROR] templates\room.html NOT FOUND!
)

echo.
if exist "requirements.txt" (
    echo [OK] requirements.txt exists
    findstr /C:"flask-socketio" requirements.txt >nul
    if %errorlevel% equ 0 (
        echo     [OK] Contains flask-socketio
    ) else (
        echo     [ERROR] Missing flask-socketio!
    )
) else (
    echo [ERROR] requirements.txt NOT FOUND!
)

echo.
echo ==========================================
echo   GIT STATUS
echo ==========================================
echo.
git status --short

echo.
echo ==========================================
echo   LAST 3 COMMITS
echo ==========================================
echo.
git log --oneline -3

echo.
echo ==========================================
pause
