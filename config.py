"""Configuration settings for Ping Monitoring System."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# Internal engine port for Laravel integration (runs on port 5000 as backend daemon)
DEFAULT_PORT = int(os.getenv("PORT", os.getenv("NETWORK_MONITOR_PORT", "5000")))
DEFAULT_HOST = os.getenv("NETWORK_MONITOR_HOST", "127.0.0.1")
POLL_INTERVAL_SECONDS = int(os.getenv("MONITORING_POLL_SECONDS", "30"))
