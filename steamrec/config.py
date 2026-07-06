from __future__ import annotations

import os
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("STEAMREC_DATA_DIR", BASE_DIR / "data"))
GAME_CACHE_DB = Path(os.getenv("STEAMREC_GAME_CACHE_DB", DATA_DIR / "game_cache.sqlite"))

APP_HOST = os.getenv("STEAMREC_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("STEAMREC_PORT", "8673"))

STEAM_API_BASE = "https://api.steampowered.com"
STEAM_STORE_BASE = "https://store.steampowered.com"
STEAM_STORE_LANGUAGE = os.getenv("STEAMREC_STORE_LANGUAGE", "schinese")

HTTP_TIMEOUT_SECONDS = float(os.getenv("STEAMREC_HTTP_TIMEOUT", "20"))
CACHE_TTL_SECONDS = int(os.getenv("STEAMREC_CACHE_TTL_SECONDS", str(3 * 24 * 60 * 60)))
GAME_RECORD_CACHE_VERSION = 7

DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45"))
DEEPSEEK_API_KEY = ""
local_config = BASE_DIR / "配置.md"
if local_config.exists():
    match = re.search(r'"deepseek_api_key"\s*:\s*"([^"]+)"', local_config.read_text(encoding="utf-8"))
    if match:
        DEEPSEEK_API_KEY = match.group(1)
if not DEEPSEEK_API_KEY:
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
