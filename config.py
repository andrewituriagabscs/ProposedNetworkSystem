"""Configuration settings for Ping Monitoring System."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Automatically read environment variables from .env if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass

# Internal engine port for Laravel integration (runs on port 5001 for Proposed system)
DEFAULT_PORT = int(os.getenv("PORT", os.getenv("NETWORK_MONITOR_PORT", "5001")))
DEFAULT_HOST = os.getenv("NETWORK_MONITOR_HOST", "127.0.0.1")
POLL_INTERVAL_SECONDS = int(os.getenv("MONITORING_POLL_SECONDS", "30"))
