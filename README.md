# Windows Locker

A client-server application that locks Windows workstations and manages DNS blocking for YouTube based on API responses.

## Architecture

- **Client**: Windows application that locks workstations and manages DNS
- **Server**: FastAPI server that manages client configurations and provides endpoints

## Server Setup

### Installation (using uv)
```cmd
cd server
uv sync
```

### Running the Server
```cmd
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`

### API Documentation
Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Client Setup

### Installation (using uv)
```cmd
cd client
uv sync
```

### Running the Client
With client name:
```cmd
uv run python windows_locker.py "my-pc-name"
```

Without client name (uses hostname):
```cmd
uv run python windows_locker.py
```

## API Endpoints

### Client Management

#### List All Clients
```http
GET /clients
```

#### Get Unlock Status
```http
GET /client/{client_name}/unlock-status
Response: {"client_name": "pc1", "unlock": false, "last_updated": "..."}
```

#### Set Unlock Status
```http
POST /client/{client_name}/unlock-status?unlock_allowed=true
```

#### Get YouTube Timer
```http
GET /client/{client_name}/youtube-timer
Response: {"client_name": "pc1", "timer_seconds": 300, "last_updated": "..."}
```

#### Set YouTube Timer
```http
POST /client/{client_name}/youtube-timer?timer_seconds=600
```

#### Configure Client (all settings)
```http
POST /clients/{client_name}/configure
Content-Type: application/json
{
    "unlock_allowed": false,
    "youtube_timer_seconds": 300
}
```

#### Delete Client
```http
DELETE /client/{client_name}
```

## Usage Examples

### 1. Start the Server
```cmd
cd server
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Configure Clients using curl

**Unlock a PC:**
```cmd
curl -X POST "http://localhost:8000/client/office-pc/unlock-status?unlock_allowed=true"
```

**Set YouTube timer to 10 minutes:**
```cmd
curl -X POST "http://localhost:8000/client/office-pc/youtube-timer?timer_seconds=600"
```

**Configure both settings:**
```cmd
curl -X POST "http://localhost:8000/clients/office-pc/configure" \
     -H "Content-Type: application/json" \
     -d '{"unlock_allowed": false, "youtube_timer_seconds": 300}'
```

**List all clients:**
```cmd
curl "http://localhost:8000/clients"
```

### 3. Start Client Applications

**On PC 1:**
```cmd
cd client
uv run python windows_locker.py "office-pc"
```

**On PC 2:**
```cmd
cd client  
uv run python windows_locker.py "home-pc"
```

## Data Persistence

The server saves client configurations to `client_configs.json` in the server directory. This file is automatically loaded on startup and saved when changes are made.

## Running as Services

### Server Service (Windows)
Using NSSM:
```cmd
nssm install WindowsLockerServer uvicorn --host 0.0.0.0 --port 8000 main:app
nssm start WindowsLockerServer
```

### Client Service (Windows)
```cmd
nssm install WindowsLockerClient "C:\path\to\uv.exe" run "C:\path\to\client\windows_locker.py" "pc-name"
nssm start WindowsLockerClient
```

## Network Configuration

- By default, server runs on port 8000
- Update `SERVER_URL` in `client/windows_locker.py` to point to your server
- Ensure firewall allows traffic on port 8000 between clients and server

## Security Considerations

- In production, add authentication to API endpoints
- Use HTTPS for API communications
- Consider using environment variables for configuration
- Restrict API access to trusted networks

## Logging

Both client and server provide console logging. For production, consider:
- Adding file logging
- Using centralized logging systems
- Implementing log rotation