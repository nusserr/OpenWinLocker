# Build script for Windows Locker Client
# Run this on Windows with Python installed

# Install dependencies
pip install pyinstaller requests

# Build the exe (onefile for easier distribution)
pyinstaller --onefile --name WindowsLocker client/windows_locker.py

# Output will be in dist/WindowsLocker.exe
