from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("STEAMREC_DATA_DIR", BASE_DIR / "data"))
GAME_CACHE_DB = Path(os.getenv("STEAMREC_GAME_CACHE_DB", DATA_DIR / "game_cache.sqlite"))

APP_HOST = os.getenv("STEAMREC_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("STEAMREC_PORT", "8673"))

STEAM_API_BASE = "https://api.steampowered.com"
STEAM_STORE_BASE = "https://store.steampowered.com"

HTTP_TIMEOUT_SECONDS = float(os.getenv("STEAMREC_HTTP_TIMEOUT", "20"))
CACHE_TTL_SECONDS = int(os.getenv("STEAMREC_CACHE_TTL_SECONDS", str(3 * 24 * 60 * 60)))
