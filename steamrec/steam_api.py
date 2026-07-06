from __future__ import annotations

import asyncio
from collections.abc import Iterable
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .cache import GameCache
from .config import GAME_RECORD_CACHE_VERSION, HTTP_TIMEOUT_SECONDS, STEAM_API_BASE, STEAM_STORE_BASE, STEAM_STORE_LANGUAGE
from .localization import display_name
from .models import GameRecord, OwnedGame, PlayerProfile


MULTIPLAYER_CATEGORY_IDS = {1, 9, 20, 27, 36, 38, 39, 44, 48, 49}
NOISE_TAGS = {
    "single-player",
    "steam achievements",
    "steam trading cards",
    "steam cloud",
    "full controller support",
    "partial controller support",
    "remote play on phone",
    "remote play on tablet",
    "remote play on tv",
    "单人",
    "steam 成就",
    "steam 集换式卡牌",
    "steam 云",
    "完全支持控制器",
    "部分支持控制器",
    "在手机上远程畅玩",
    "在平板上远程畅玩",
    "在电视上远程畅玩",
    "family sharing",
    "家庭共享",
    "remote play together",
    "远程同乐",
    "multi-player",
    "co-op",
    "online co-op",
    "pvp",
    "online pvp",
    "shared/split screen",
    "lan co-op",
    "lan pvp",
    "多人",
    "合作",
    "在线合作",
    "玩家对战",
    "线上玩家对战",
    "局域网玩家对战",
    "局域网合作",
    "同屏/分屏",
    "跨平台多人",
    "steam workshop",
    "steam 创意工坊",
    "in-app purchases",
    "应用内购买",
    "free to play",
    "免费开玩",
    "custom volume controls",
    "自定义音量控制",
    "adjustable text size",
    "可调整文字大小",
    "camera comfort",
    "视角舒适度",
    "chat text-to-speech",
    "聊天文字转语音",
    "chat speech-to-text",
    "聊天语音转文字",
    "color alternatives",
    "颜色替代方案",
    "playable without timed input",
    "可在没有限时输入的情况下游玩",
}


class SteamApiError(RuntimeError):
    pass


class SteamClient:
    def __init__(self, cache: GameCache | None = None) -> None:
        self.cache = cache or GameCache()

    async def close(self) -> None:
        return None

    async def owned_games(self, api_key: str, steamid: str) -> PlayerProfile:
        params = {
            "key": api_key,
            "steamid": steamid,
            "format": "json",
            "include_appinfo": 1,
            "include_played_free_games": 1,
        }
        url = f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v0001/"
        try:
            body = await asyncio.to_thread(_get_json, url, params)
        except PermissionError:
            return PlayerProfile(steamid=steamid, games=[], valid=False, reason="Steam API key denied or profile is private")
        body = body.get("response", {})
        games = [
            OwnedGame(
                appid=int(item["appid"]),
                name=item.get("name", ""),
                playtime_forever=int(item.get("playtime_forever", 0)),
            )
            for item in body.get("games", [])
        ]
        if len(games) < 4 or sum(g.playtime_forever for g in games) < 120:
            return PlayerProfile(steamid=steamid, games=games, valid=False, reason="visible library is too small for group taste modeling")
        return PlayerProfile(steamid=steamid, games=games)

    async def app_details(self, appid: int, source_marks: list[str] | None = None) -> GameRecord | None:
        cached = self.cache.get_game(appid)
        if cached and cached.get("language") == STEAM_STORE_LANGUAGE and cached.get("cache_version") == GAME_RECORD_CACHE_VERSION:
            cached["source_marks"] = sorted(set(cached.get("source_marks", []) + (source_marks or [])))
            return GameRecord(**cached)

        detail_url = f"{STEAM_STORE_BASE}/api/appdetails"
        review_url = f"{STEAM_STORE_BASE}/appreviews/{appid}"
        detail_task = asyncio.to_thread(
            _get_json,
            detail_url,
            {"appids": appid, "filters": "basic,categories,genres,release_date", "l": STEAM_STORE_LANGUAGE},
        )
        review_task = asyncio.to_thread(
            _get_json,
            review_url,
            {"json": 1, "filter": "recent", "language": "all", "purchase_type": "all", "num_per_page": 0},
        )
        detail_response, review_response = await asyncio.gather(detail_task, review_task, return_exceptions=True)

        if isinstance(detail_response, Exception):
            return None
        detail_body = detail_response.get(str(appid), {})
        if not detail_body.get("success"):
            return None
        data = detail_body.get("data", {})
        if data.get("type") != "game":
            return None

        categories = data.get("categories") or []
        genres = data.get("genres") or []
        category_names = [item.get("description", "") for item in categories if item.get("description")]
        genre_names = [item.get("description", "") for item in genres if item.get("description")]
        tags = _normalize_tags(genre_names)

        review_percent = None
        review_count = None
        if not isinstance(review_response, Exception):
            summary = review_response.get("query_summary", {})
            review_percent = summary.get("review_score")
            review_count = summary.get("total_reviews")

        record = GameRecord(
            appid=appid,
            name=display_name(appid, data.get("name", f"App {appid}")),
            tags=tags,
            categories=category_names,
            genres=genre_names,
            release_date=(data.get("release_date") or {}).get("date"),
            coming_soon=bool((data.get("release_date") or {}).get("coming_soon", False)),
            review_percent=review_percent,
            review_count=review_count,
            capsule_image=data.get("capsule_image"),
            store_url=f"{STEAM_STORE_BASE}/app/{appid}",
            source_marks=source_marks or [],
            max_players_hint=_max_players_hint(category_names),
            language=STEAM_STORE_LANGUAGE,
            cache_version=GAME_RECORD_CACHE_VERSION,
        )
        self.cache.put_game(appid, record.to_dict())
        return record

    async def app_details_many(self, appids: Iterable[int], source_map: dict[int, list[str]] | None = None) -> list[GameRecord]:
        sem = asyncio.Semaphore(8)

        async def fetch(appid: int) -> GameRecord | None:
            async with sem:
                return await self.app_details(appid, (source_map or {}).get(appid, []))

        records = await asyncio.gather(*(fetch(appid) for appid in appids))
        return [record for record in records if record is not None]


def is_multiplayer(record: GameRecord) -> bool:
    text = " ".join(record.categories).lower()
    return any(
        token in text
        for token in (
            "multi-player",
            "co-op",
            "mmo",
            "shared/split screen",
            "pvp",
            "online",
            "多人",
            "合作",
            "大型多人",
            "在线",
            "玩家对战",
            "同屏",
        )
    )


def _normalize_tags(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for value in values:
        tag = value.strip()
        lowered = tag.lower()
        if not tag or lowered in seen or lowered in NOISE_TAGS:
            continue
        seen.add(lowered)
        tags.append(tag)
    return tags[:24]


def _max_players_hint(categories: list[str]) -> int | None:
    lowered = " ".join(categories).lower()
    if "mmo" in lowered or "大型多人" in lowered:
        return 16
    if "co-op" in lowered or "multi-player" in lowered or "合作" in lowered or "多人" in lowered:
        return 4
    return None


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    full_url = f"{url}?{urlencode(params)}"
    request = Request(full_url, headers={"User-Agent": "steam-group-rec/0.1"})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        if getattr(exc, "code", None) == 403:
            raise PermissionError from exc
        raise
