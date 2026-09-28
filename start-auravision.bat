@echo off
title AURAVISION - Offline AI Mission Control Launcher
echo ========================================================
echo   AURAVISION - AI Human Activity Recognition (ISRO / SIH)
echo   Starting Offline LAN Backend + React Frontend...
echo ========================================================

set "PYTHON_EXE=C:\Users\Harshitha\AppData\Local\Programs\Python\Python311\python.exe"
set "NODE_DIR=C:\Users\Harshitha\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64"
set "PATH=%NODE_DIR%;%PATH%"

:: 1. Launch FastAPI Backend on 0.0.0.0:8000
echo [1/2] Starting FastAPI Backend on 0.0.0.0:8000...
start "AURAVISION Backend (0.0.0.0:8000)" cmd /k "cd /d "%~dp0backend" && "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: 2. Launch Vite React Frontend on 0.0.0.0:3000
echo [2/2] Starting React + TypeScript Frontend on 0.0.0.0:3000...
start "AURAVISION Frontend (0.0.0.0:3000)" cmd /k "cd /d "%~dp0frontend" && "%NODE_DIR%\npm.cmd" run dev"

timeout /t 3 >nul

:: 3. Open browser to AURAVISION Frontend
echo Opening http://localhost:3000 in your browser...
start http://localhost:3000

echo ========================================================
echo   AURAVISION is now running in full offline LAN mode!
echo   Frontend URL: http://localhost:3000
echo   Backend URL:  http://localhost:8000
echo ========================================================
