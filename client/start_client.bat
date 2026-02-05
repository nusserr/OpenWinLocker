@echo off
echo Starting Windows Locker Client...
set /p client_name="Enter client name (or press Enter to use hostname): "
if "%client_name%"=="" (
    uv run python windows_locker.py
) else (
    uv run python windows_locker.py "%client_name%"
)
pause