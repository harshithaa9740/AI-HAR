@echo off
setlocal
set "PYTHON_EXE=C:\Users\Harshitha\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python 3.11 was not found at %PYTHON_EXE%
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0backend\scripts\generate_synthetic_mission_data.py" %*
endlocal
