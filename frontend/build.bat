@echo off
set "NODE_DIR=C:\Users\Harshitha\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64"
set "PATH=%NODE_DIR%;%PATH%"
cd /d "c:\Users\Harshitha\Desktop\SIH\frontend"
call "%NODE_DIR%\npm.cmd" run build
