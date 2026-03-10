# Build script for Windows Locker Client
# Run this on Windows with Python installed

# Install dependencies
uv pip install pyinstaller requests

# Build the exe (onefile for easier distribution)
uv pyinstaller --onefile --name WindowsLocker client/windows_locker.py

# Output will be in dist/WindowsLocker.exe
