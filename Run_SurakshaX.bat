@echo off
title SurakshaX Safety AI Server & Live Public Tunnel
cd /d "%~dp0"

echo ================================================================
echo  Oil India Limited • SurakshaX Safety AI Launcher
echo ================================================================

py -3.12 scripts\launch_services.py

echo.
echo ================================================================
echo  SURAKSHAX IS ONLINE & READY!
echo.
echo  1. Localhost Link : http://127.0.0.1:5000
echo  2. Public Live URL: https://define-stoplight-olympics.ngrok-free.dev
echo.
echo  The portal has opened in your web browser.
echo ================================================================
echo.
pause
