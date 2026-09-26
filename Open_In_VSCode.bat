@echo off
title Open SurakshaX in Visual Studio Code
cd /d "%~dp0"

echo ================================================================
echo  Opening SurakshaX Codebase in Visual Studio Code...
echo ================================================================

code .

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [NOTE] 'code' command not found in system PATH.
    echo Trying default installation location...
    "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" "%~dp0"
)

echo.
echo [OK] Visual Studio Code launched!
timeout /t 2 >nul
