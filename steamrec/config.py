from __future__ import annotations

import os
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("STEAMREC_DATA_DIR", BASE_DIR / "data"))
GAME_CACHE_DB = Path(os.getenv("STEAMREC_GAME_CACHE_DB", DATA_DIR / "game_cache.sqlite"))
ANALYTICS_DB = Path(os.getenv("STEAMREC_ANALYTICS_DB", DATA_DIR / "analytics.sqlite"))

APP_HOST = os.getenv("STEAMREC_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("STEAMREC_PORT", "8673"))

STEAM_API_BASE = "https://api.steampowered.com"
STEAM_STORE_BASE = "https://store.steampowered.com"
STEAM_STORE_LANGUAGE = os.getenv("STEAMREC_STORE_LANGUAGE", "schinese")

HTTP_TIMEOUT_SECONDS = float(os.getenv("STEAMREC_HTTP_TIMEOUT", "20"))
CACHE_TTL_SECONDS = int(os.getenv("STEAMREC_CACHE_TTL_SECONDS", str(3 * 24 * 60 * 60)))
GAME_RECORD_CACHE_VERSION = 10

# 心愿单加成上限：按 (命中人数/总人数)^2 的陡曲线取值，1 人很小、2 人明显、全员接近上限。
WISHLIST_BONUS_MAX = float(os.getenv("STEAMREC_WISHLIST_BONUS", "0.35"))
# 只被 1 人加心愿单的游戏，每人最多取最近加入的 N 个进候选，控制抓取成本。
WISHLIST_SOLO_LIMIT = int(os.getenv("STEAMREC_WISHLIST_SOLO_LIMIT", "15"))
TAG_DICTIONARY_TTL_SECONDS = int(os.getenv("STEAMREC_TAG_DICTIONARY_TTL", str(7 * 24 * 60 * 60)))
CANDIDATE_POOL_TTL_SECONDS = int(os.getenv("STEAMREC_CANDIDATE_POOL_TTL", str(12 * 60 * 60)))
INGEST_RECENT_MONTHS = int(os.getenv("STEAMREC_INGEST_RECENT_MONTHS", "18"))

# appdetails 拉取失败(429/非游戏/下架)的负缓存，避免每个请求都重试同一批坏 appid。
STEAM_MISS_TTL_SECONDS = int(os.getenv("STEAMREC_STEAM_MISS_TTL", str(6 * 60 * 60)))

# 并发防护：Steam 出站并发是全进程共享的上限，不随请求数放大。
STEAM_FETCH_CONCURRENCY = int(os.getenv("STEAMREC_STEAM_FETCH_CONCURRENCY", "8"))
MAX_CONCURRENT_RECOMMENDATIONS = int(os.getenv("STEAMREC_MAX_CONCURRENT_RECS", "4"))
RECOMMENDATION_TIMEOUT_SECONDS = float(os.getenv("STEAMREC_RECOMMENDATION_TIMEOUT", "240"))

# 访问统计：令牌不进 git，本地从被忽略的 配置.md 读取，远端从 /etc/steam-group-rec.env 注入。
# 令牌为空时 /stats 直接 404，功能整体关闭。
STATS_TZ_OFFSET_HOURS = int(os.getenv("STEAMREC_STATS_TZ", "8"))
STATS_TOKEN = os.getenv("STEAMREC_STATS_TOKEN", "")
if not STATS_TOKEN:
    _local_config = BASE_DIR / "配置.md"
    if _local_config.exists():
        _match = re.search(r"stats_token[：:]\s*([A-Za-z0-9_-]+)", _local_config.read_text(encoding="utf-8"))
        if _match:
            STATS_TOKEN = _match.group(1)

# 兜底 Steam Web API Key：用户网页留空时使用（站长自己的 key，站长知情同意部署到服务器）。
# 本地从 配置.md 的 `steamapi：` 行读取，远端从 env 注入。
FALLBACK_STEAM_API_KEY = os.getenv("STEAMREC_FALLBACK_STEAM_KEY", "")
if not FALLBACK_STEAM_API_KEY:
    _local_config = BASE_DIR / "配置.md"
    if _local_config.exists():
        _match = re.search(r"steamapi[：:]\s*([A-Za-z0-9]+)", _local_config.read_text(encoding="utf-8"))
        if _match:
            FALLBACK_STEAM_API_KEY = _match.group(1)

# DeepSeek key 由用户在网页填写、随单次请求转发，服务端不持有。
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45"))
