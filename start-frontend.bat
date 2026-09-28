@echo off
title AURAVISION - React TypeScript Frontend (LAN Mode)
set "NODE_DIR=C:\Users\Harshitha\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64"
set "PATH=%NODE_DIR%;%PATH%"
cd /d "%~dp0frontend"
echo ========================================================
echo   AURAVISION React + TypeScript Frontend (Offline LAN)
echo   Local URL:    http://localhost:3000
echo   Network URL:  http://0.0.0.0:3000
echo ========================================================
call "%NODE_DIR%\npm.cmd" run dev
