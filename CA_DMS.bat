@echo off
setlocal enabledelayedexpansion
title Document Management System - Network Access
color 0A

echo.
echo ========================================
echo   DOCUMENT MANAGEMENT SYSTEM
echo   Enhanced Network Access Startup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python and try again.
    pause
    exit /b 1
)

REM Check if required files exist
if not exist "app.py" (
    echo ❌ app.py not found in current directory
    echo Please run this script from the project directory.
    pause
    exit /b 1
)

REM Check if requirements are installed
echo 🔍 Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Flask not found. Installing requirements...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install requirements
        pause
        exit /b 1
    )
)

echo ✅ Dependencies check complete
echo.

REM Get network information
echo 🌐 Detecting network configuration...
set ip=
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "IPv4"') do (
    set ip=%%i
    set ip=!ip: =!
    if not "!ip!"=="" (
        echo 📍 Found IP: !ip!
        goto :ip_found
    )
)
:ip_found

echo.
echo 🚀 Starting Document Management System...
echo.
echo 💡 Network Information:
echo    - Local access: http://localhost:5000
echo    - Network access: http://!ip!:5000
echo    - Detailed info: http://!ip!:5000/network_info
echo.
echo 📱 Other devices can access using the network URL above
echo 🔄 The application will automatically open in your browser
echo.

REM Start the enhanced startup script
python start_app_with_ip.py

if errorlevel 1 (
    echo.
    echo ❌ Application failed to start
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ✅ Application started successfully!
echo 🌐 Access URLs:
echo    - Local: http://localhost:5000
echo    - Network: http://!ip!:5000
echo.
pause

