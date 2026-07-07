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
STEAM_STORE_LANGUAGE = os.getenv("STEAMREC_STORE_LANGUAGE", "schinese")

HTTP_TIMEOUT_SECONDS = float(os.getenv("STEAMREC_HTTP_TIMEOUT", "20"))
CACHE_TTL_SECONDS = int(os.getenv("STEAMREC_CACHE_TTL_SECONDS", str(3 * 24 * 60 * 60)))
GAME_RECORD_CACHE_VERSION = 8
CANDIDATE_POOL_TTL_SECONDS = int(os.getenv("STEAMREC_CANDIDATE_POOL_TTL", str(12 * 60 * 60)))
INGEST_RECENT_MONTHS = int(os.getenv("STEAMREC_INGEST_RECENT_MONTHS", "18"))

# appdetails 拉取失败(429/非游戏/下架)的负缓存，避免每个请求都重试同一批坏 appid。
STEAM_MISS_TTL_SECONDS = int(os.getenv("STEAMREC_STEAM_MISS_TTL", str(6 * 60 * 60)))

# 并发防护：Steam 出站并发是全进程共享的上限，不随请求数放大。
STEAM_FETCH_CONCURRENCY = int(os.getenv("STEAMREC_STEAM_FETCH_CONCURRENCY", "8"))
MAX_CONCURRENT_RECOMMENDATIONS = int(os.getenv("STEAMREC_MAX_CONCURRENT_RECS", "4"))
RECOMMENDATION_TIMEOUT_SECONDS = float(os.getenv("STEAMREC_RECOMMENDATION_TIMEOUT", "240"))

# DeepSeek key 由用户在网页填写、随单次请求转发，服务端不持有。
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45"))
