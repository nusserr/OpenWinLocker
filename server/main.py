from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Optional
import time
from datetime import datetime, timedelta
import json
import os

app = FastAPI(
    title="Windows Locker Server",
    description="API for managing Windows workstation locks and DNS blocking",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Data models
class ClientConfig(BaseModel):
    unlock_allowed: bool = False
    youtube_timer_seconds: int = 300
    last_updated: Optional[datetime] = None


class LockRequest(BaseModel):
    client_name: str
    unlock_allowed: bool


class YouTubeTimerRequest(BaseModel):
    client_name: str
    timer_seconds: int


# In-memory storage for client configurations
# In production, this should be replaced with a database
client_configs: Dict[str, ClientConfig] = {}

# Configuration file path
CONFIG_FILE = "client_configs.json"


def load_configs():
    """Load client configurations from file"""
    global client_configs
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                for client_name, config_data in data.items():
                    client_configs[client_name] = ClientConfig(
                        unlock_allowed=config_data.get("unlock_allowed", False),
                        youtube_timer_seconds=config_data.get(
                            "youtube_timer_seconds", 300
                        ),
                        last_updated=datetime.fromisoformat(config_data["last_updated"])
                        if config_data.get("last_updated")
                        else None,
                    )
            print(f"Loaded {len(client_configs)} client configurations")
        except Exception as e:
            print(f"Error loading configs: {e}")


def save_configs():
    """Save client configurations to file"""
    try:
        data = {}
        for client_name, config in client_configs.items():
            data[client_name] = {
                "unlock_allowed": config.unlock_allowed,
                "youtube_timer_seconds": config.youtube_timer_seconds,
                "last_updated": config.last_updated.isoformat()
                if config.last_updated
                else None,
            }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving configs: {e}")


@app.on_event("startup")
async def startup_event():
    load_configs()


@app.on_event("shutdown")
async def shutdown_event():
    save_configs()


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api")
async def api_root():
    return {"message": "Windows Locker Server API is running"}


@app.get("/clients")
async def list_clients():
    """List all registered clients and their configurations"""
    return {
        "clients": [
            {
                "name": name,
                "unlock_allowed": config.unlock_allowed,
                "youtube_timer_seconds": config.youtube_timer_seconds,
                "last_updated": config.last_updated.isoformat()
                if config.last_updated
                else None,
            }
            for name, config in client_configs.items()
        ],
        "total_clients": len(client_configs),
    }


@app.get("/client/{client_name}/unlock-status")
async def get_unlock_status(client_name: str):
    """Get unlock status for a specific client"""
    if client_name not in client_configs:
        # Auto-register new clients with default locked state
        client_configs[client_name] = ClientConfig(
            unlock_allowed=False, youtube_timer_seconds=300, last_updated=datetime.now()
        )
        save_configs()

    config = client_configs[client_name]
    return {
        "client_name": client_name,
        "unlock": config.unlock_allowed,
        "last_updated": config.last_updated.isoformat()
        if config.last_updated
        else None,
    }


@app.post("/client/{client_name}/unlock-status")
async def set_unlock_status(client_name: str, unlock_allowed: bool):
    """Set unlock status for a specific client"""
    if client_name not in client_configs:
        client_configs[client_name] = ClientConfig()

    client_configs[client_name].unlock_allowed = unlock_allowed
    client_configs[client_name].last_updated = datetime.now()
    save_configs()

    return {
        "client_name": client_name,
        "unlock": unlock_allowed,
        "message": f"Unlock status updated for {client_name}",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/client/{client_name}/youtube-timer")
async def get_youtube_timer(client_name: str):
    """Get YouTube timer for a specific client"""
    if client_name not in client_configs:
        # Auto-register new clients with default timer
        client_configs[client_name] = ClientConfig(
            unlock_allowed=False, youtube_timer_seconds=300, last_updated=datetime.now()
        )
        save_configs()

    config = client_configs[client_name]
    return {
        "client_name": client_name,
        "timer_seconds": config.youtube_timer_seconds,
        "last_updated": config.last_updated.isoformat()
        if config.last_updated
        else None,
    }


@app.post("/client/{client_name}/youtube-timer")
async def set_youtube_timer(client_name: str, timer_seconds: int):
    """Set YouTube timer for a specific client"""
    if timer_seconds < 0:
        raise HTTPException(status_code=400, detail="Timer seconds must be positive")

    if client_name not in client_configs:
        client_configs[client_name] = ClientConfig()

    client_configs[client_name].youtube_timer_seconds = timer_seconds
    client_configs[client_name].last_updated = datetime.now()
    save_configs()

    return {
        "client_name": client_name,
        "timer_seconds": timer_seconds,
        "message": f"YouTube timer updated for {client_name}",
        "timestamp": datetime.now().isoformat(),
    }


@app.delete("/client/{client_name}")
async def delete_client(client_name: str):
    """Delete a client configuration"""
    if client_name not in client_configs:
        raise HTTPException(status_code=404, detail="Client not found")

    del client_configs[client_name]
    save_configs()

    return {"message": f"Client {client_name} deleted successfully"}


# Management endpoints for bulk operations
@app.post("/clients/{client_name}/configure")
async def configure_client(client_name: str, config: ClientConfig):
    """Configure all settings for a client at once"""
    config.last_updated = datetime.now()
    client_configs[client_name] = config
    save_configs()

    return {
        "client_name": client_name,
        "message": "Client configured successfully",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
