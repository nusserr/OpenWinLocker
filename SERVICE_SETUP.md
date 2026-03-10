# Windows Locker - Build & Service Setup

## Prerequisites

1. **Windows PC** - This only works on Windows
2. **Python 3.7+** - Install on the Windows machine
3. **NSSM** - Download from https://nssm.cc/download

## Step 1: Build the Executable

Run on your Windows machine:

```cmd
pip install pyinstaller requests
pyinstaller --onefile --name WindowsLocker client/windows_locker.py
```

The exe will be created at `dist/WindowsLocker.exe`

## Step 2: Install as Windows Service

```cmd
install_service.bat <client_name> <server_url>
```

Example:
```cmd
install_service.bat PC01 http://192.168.1.100:8000
```

## Step 3: Start the Service

```cmd
net start WindowsLocker
```

## Service Management

| Action | Command |
|--------|---------|
| Start | `net start WindowsLocker` |
| Stop | `net stop WindowsLocker` |
| Status | `sc query WindowsLocker` |
| Uninstall | `nssm remove WindowsLocker` |
| View logs | Event Viewer → Windows Logs → Application |

## Environment Variables

The service accepts these environment variables:
- `CLIENT_NAME` - Name of this client (defaults to hostname)
- `SERVER_URL` - URL of the lock server (defaults to http://localhost:8000)

Set these via NSSM:
```cmd
nssm set WindowsLocker AppEnvironmentExtra "CLIENT_NAME=PC01"
nssm set WindowsLocker AppEnvironmentExtra "SERVER_URL=http://192.168.1.100:8000"
```
