@echo off
setlocal
title Push AURAVISION to GitHub
echo ========================================================
echo   Pushing AURAVISION to GitHub
echo   Repository: https://github.com/harshithaa9740/AI-HAR.git
echo ========================================================
echo.
set "GIT_EXE=C:\Users\Harshitha\AppData\Local\Programs\Git\cmd\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=git"

echo Checking Git commit status...
"%GIT_EXE%" add .
"%GIT_EXE%" commit -m "Update project files" 2>nul

echo.
echo GitHub requires a Personal Access Token (Classic or Fine-Grained) to push.
echo (If you do not have one yet, generate one at https://github.com/settings/tokens)
echo.
set /p TOKEN="Enter your GitHub Personal Access Token (PAT): "

if "%TOKEN%"=="" (
    echo [ERROR] No token entered. Exiting.
    pause
    exit /b 1
)

echo.
echo Pushing to GitHub...
"%GIT_EXE%" push -u "https://%TOKEN%@github.com/harshithaa9740/AI-HAR.git" main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   SUCCESS! Project pushed to:
    echo   https://github.com/harshithaa9740/AI-HAR
    echo ========================================================
) else (
    echo.
    echo [ERROR] Failed to push. Please check your token permissions (ensure 'repo' scope is selected).
)

echo.
pause
