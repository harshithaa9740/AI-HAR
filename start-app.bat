@echo off
title AURAVISION - AI Human Activity Recognition (SIH)
echo ========================================================
echo   Starting AURAVISION AI Human Activity Recognition...
echo ========================================================
echo Opening http://localhost:8080 in your browser...
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0server.ps1"
pause
