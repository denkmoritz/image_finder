import os

class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "gis")
    DB_USER = os.getenv("DB_USER", "moritz")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "3004")
    DB_PORT = os.getenv("DB_PORT", 25432)

from pathlib import Path

# Where to cache thumbs locally
THUMB_DIR = Path("thumbs")
THUMB_DIR.mkdir(parents=True, exist_ok=True)

# How to build the remote URL for a given UUID
# Change to your real CDN/service (signed, internal, etc.)
THUMB_URL_TEMPLATE = "https://your.cdn.example/thumbs/{uid}.jpg"

# pHash + geo defaults (match your notes)
MAX_DISTANCE_M = 3.0
MAX_ANGLE_DEG = 20.0
PHASH_THRESHOLD = 8
DROP_SINGLETONS = False