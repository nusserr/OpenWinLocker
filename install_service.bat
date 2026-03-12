@echo off
REM Windows Locker Service Setup using NSSM
REM
REM Prerequisites:
REM 1. Download NSSM from https://nssm.cc/download
REM 2. Extract nssm.exe to a folder and add it to PATH, or place it next to this script
REM 3. Build the exe using build_exe.bat
REM
REM Usage:
REM   install_service.bat ^<client_name^> ^<server_url^> [^<usb_serial^]
REM
REM Example:
REM   install_service.bat PC01 http://192.168.1.100:8000
REM   install_service.bat PC01 http://192.168.1.100:8000 ABC123456789

if "%1"=="" (
    echo Usage: install_service.bat ^<client_name^> ^<server_url^> [^<usb_serial^]
    echo Example: install_service.bat PC01 http://192.168.1.100:8000
    echo Example with USB: install_service.bat PC01 http://192.168.1.100:8000 ABC123456789
    exit /b 1
)

set CLIENT_NAME=%1
set SERVER_URL=%2
set USB_SERIAL=%3

if "%SERVER_URL%"=="" (
    set SERVER_URL=http://localhost:8000
)

set SERVICE_NAME=WindowsLocker
set EXE_PATH=%~dp0dist\WindowsLocker.exe

if not exist "%EXE_PATH%" (
    echo Error: WindowsLocker.exe not found at %EXE_PATH%
    echo Please run build_exe.bat first to create the executable.
    exit /b 1
)

echo Installing WindowsLocker service...
echo   Client Name: %CLIENT_NAME%
echo   Server URL: %SERVER_URL%
if not "%USB_SERIAL%"=="" (
    echo   USB Serial: %USB_SERIAL%
)

REM Check if nssm is available
where nssm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: nssm not found in PATH
    echo Please download NSSM from https://nssm.cc/download and add it to PATH
    exit /b 1
)

REM Stop service if already running
net stop %SERVICE_NAME% >nul 2>nul

REM Delete existing service if present
nssm remove %SERVICE_NAME% confirm >nul 2>nul

REM Install service
nssm install %SERVICE_NAME% "%EXE_PATH%" "%CLIENT_NAME%"

REM Set environment variables
nssm set %SERVICE_NAME% AppEnvironmentExtra "SERVER_URL=%SERVER_URL%"
if not "%USB_SERIAL%"=="" (
    nssm set %SERVICE_NAME% AppEnvironmentExtra "ALLOWED_USB_SERIALS=%USB_SERIAL%"
)

REM Set startup to automatic
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Set display name
nssm set %SERVICE_NAME% DisplayName "Windows Locker Service"

REM Set description
nssm set %SERVICE_NAME% Description "Manages Windows workstation locking based on server commands"

echo.
echo Service installed successfully!
echo.
echo To start the service, run:
echo   net start %SERVICE_NAME%
echo.
echo To check service status:
echo   sc query %SERVICE_NAME%
echo.
echo To uninstall the service:
echo   nssm remove %SERVICE_NAME% confirm
