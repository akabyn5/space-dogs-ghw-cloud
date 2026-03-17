"""
config.py — Central configuration for Space Dogs Telemetry API
All environment variables are defined here.

You can override defaults by creating a `.env` file in this folder.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# Base directory of the API folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database path
DB_PATH = os.environ.get(
    "TELEMETRY_DB_PATH",
    os.path.join(BASE_DIR, "telemetry.db")
)

# Flask settings
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
PORT = int(os.environ.get("FLASK_PORT", "5000"))

# Rate limiting
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "60"))

# Cache settings
STATS_CACHE_TTL = float(os.environ.get("STATS_CACHE_TTL_SECS", "10"))