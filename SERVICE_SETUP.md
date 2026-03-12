# Windows Locker - Build & Service Setup

## Prerequisites

1. **Windows PC** - This only works on Windows
2. **Python 3.7+** - Install on the Windows machine
3. **NSSM** - Download from https://nssm.cc/download

## Step 1: Build the Executable

Run on your Windows machine:

```cmd
uv pip install pyinstaller requests pywin32
uv run pyinstaller --onefile --name WindowsLocker client/windows_locker.py
```

The exe will be created at `dist/WindowsLocker.exe`

## Step 2: Find Your USB Serial Number

To get your USB stick's serial number, run this command on Windows:

```cmd
wmic path Win32_PnPEntity where "Service='USBSTOR'" get DeviceID
```

The serial will appear at the end of the device ID (after the last `\`).

## Step 3: Install as Windows Service

```cmd
install_service.bat <client_name> <server_url> [usb_serial]
```

Examples:
```cmd
install_service.bat PC01 http://192.168.1.100:8000
install_service.bat PC01 http://192.168.1.100:8000 ABC123456789
```

## Step 4: Start the Service

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
- `ALLOWED_USB_SERIALS` - Comma-separated USB serials that keep PC unlocked

Set these via NSSM:
```cmd
nssm set WindowsLocker AppEnvironmentExtra "CLIENT_NAME=PC01"
nssm set WindowsLocker AppEnvironmentExtra "SERVER_URL=http://192.168.1.100:8000"
nssm set WindowsLocker AppEnvironmentExtra "ALLOWED_USB_SERIALS=ABC123,DEF456"
```

## How USB Unlock Works

1. When the configured USB stick is inserted, the PC will stay unlocked (or unlock if locked)
2. When the USB stick is removed, the PC will lock (respecting server commands)
3. If no USB serial is configured, USB unlock is disabled
