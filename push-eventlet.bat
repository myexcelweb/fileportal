@echo off
setlocal enabledelayedexpansion
title FilePortal - EVENTLET SWITCH
color 0B

echo ==========================================
echo   SWITCHING TO EVENTLET
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/3] Adding modified files...
git add app.py requirements.txt render.yaml

echo [2/3] Committing...
git commit -m "Switch to Eventlet: Updated app.py, requirements, and render.yaml"

echo [3/3] Pushing to GitHub...
git push origin main

echo.
echo ==========================================
echo   DEPLOYMENT SENT
echo ==========================================
echo IMPORTANT:
echo Go to Render Dashboard -> Manual Deploy
echo Select "Clear Build Cache & Deploy"
echo ==========================================
pause