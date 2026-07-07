from __future__ import annotations

import asyncio
from collections.abc import Iterable
import json
import re
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .cache import GameCache
from .config import (
    GAME_RECORD_CACHE_VERSION,
    HTTP_TIMEOUT_SECONDS,
    STEAM_API_BASE,
    STEAM_FETCH_CONCURRENCY,
    STEAM_MISS_TTL_SECONDS,
    STEAM_STORE_BASE,
    STEAM_STORE_LANGUAGE,
)
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


class SteamKeyError(RuntimeError):
    """API key 本身的问题（无效/限额），区别于玩家资料私密等用户数据问题。"""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind  # "denied" | "rate_limited"


# 全进程共享的 Steam 出站并发上限；依赖 app.py 的单一事件循环，多个并发请求共用同一配额。
_fetch_semaphore: asyncio.Semaphore | None = None


def _steam_semaphore() -> asyncio.Semaphore:
    global _fetch_semaphore
    if _fetch_semaphore is None:
        _fetch_semaphore = asyncio.Semaphore(STEAM_FETCH_CONCURRENCY)
    return _fetch_semaphore


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
        except PermissionError as exc:
            # GetOwnedGames 的 403/401 是 key 无效；私密资料是 200 + 空 response，不走这里。
            raise SteamKeyError("denied") from exc
        except Exception as exc:
            if getattr(exc, "code", None) == 429:
                raise SteamKeyError("rate_limited") from exc
            raise
        body = body.get("response", {})
        games = [
            OwnedGame(
                appid=int(item["appid"]),
                name=item.get("name", ""),
                playtime_forever=int(item.get("playtime_forever", 0)),
                playtime_2weeks=int(item.get("playtime_2weeks", 0)),
            )
            for item in body.get("games", [])
        ]
        if not games:
            return PlayerProfile(steamid=steamid, games=[], valid=False, reason="库存私密或为空，无法读取")
        if len(games) < 4 or sum(g.playtime_forever for g in games) < 120:
            return PlayerProfile(steamid=steamid, games=games, valid=False, reason="可见库存太小，不足以参与口味建模")
        return PlayerProfile(steamid=steamid, games=games)

    async def friend_list(self, api_key: str, steamid: str) -> list[str] | None:
        """公开好友列表的 SteamID；好友列表私密返回 None；key 问题抛 SteamKeyError。"""
        url = f"{STEAM_API_BASE}/ISteamUser/GetFriendList/v0001/"
        try:
            body = await asyncio.to_thread(_get_json, url, {"key": api_key, "steamid": steamid, "relationship": "friend"})
        except PermissionError as exc:
            # GetFriendList 对私密好友列表和坏 key 都返回 401：用一次便宜的 summaries 调用区分。
            try:
                await self.player_summaries(api_key, [steamid])
            except Exception:
                raise SteamKeyError("denied") from exc
            return None
        except Exception as exc:
            if getattr(exc, "code", None) == 429:
                raise SteamKeyError("rate_limited") from exc
            raise
        friends = body.get("friendslist", {}).get("friends", [])
        return [str(item["steamid"]) for item in friends if item.get("steamid")][:300]

    async def player_summaries(self, api_key: str, steamids: list[str]) -> dict[str, dict[str, object]]:
        """批量玩家概要 {steamid: {name, avatar, visible}}；visible=资料公开(可读库存的前提)。"""
        url = f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v0002/"
        result: dict[str, dict[str, object]] = {}
        for start in range(0, len(steamids), 100):
            chunk = steamids[start : start + 100]
            body = await asyncio.to_thread(_get_json, url, {"key": api_key, "steamids": ",".join(chunk)})
            for player in body.get("response", {}).get("players", []):
                result[str(player["steamid"])] = {
                    "name": player.get("personaname", ""),
                    "avatar": player.get("avatarmedium") or player.get("avatar") or "",
                    "visible": player.get("communityvisibilitystate") == 3,
                }
        return result

    async def wishlist(self, steamid: str) -> list[int]:
        """公开心愿单的 appid 列表，按加入时间新到旧；私密或失败返回空。"""
        url = f"{STEAM_API_BASE}/IWishlistService/GetWishlist/v1/"
        try:
            body = await asyncio.to_thread(_get_json, url, {"steamid": steamid})
        except Exception:
            return []
        items = body.get("response", {}).get("items", [])
        items.sort(key=lambda item: item.get("date_added", 0), reverse=True)
        return [int(item["appid"]) for item in items if item.get("appid")]

    async def resolve_steam_id(self, api_key: str, entry: str) -> str | None:
        """把用户输入(SteamID64 / 主页链接 / 自定义名)解析成 SteamID64；解析失败返回 None。"""
        entry = entry.strip().rstrip("/")
        if re.fullmatch(r"\d{17}", entry):
            return entry
        profile_match = re.search(r"steamcommunity\.com/profiles/(\d{17})", entry)
        if profile_match:
            return profile_match.group(1)
        vanity = None
        vanity_match = re.search(r"steamcommunity\.com/id/([\w.-]+)", entry)
        if vanity_match:
            vanity = vanity_match.group(1)
        elif re.fullmatch(r"[\w.-]{2,32}", entry):
            vanity = entry
        if not vanity:
            return None
        url = f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v0001/"
        try:
            body = await asyncio.to_thread(_get_json, url, {"key": api_key, "vanityurl": vanity})
        except PermissionError as exc:
            raise SteamKeyError("denied") from exc
        except Exception as exc:
            if getattr(exc, "code", None) == 429:
                raise SteamKeyError("rate_limited") from exc
            return None
        response = body.get("response", {})
        if response.get("success") == 1:
            return str(response.get("steamid"))
        return None

    def _cached_record(self, appid: int, source_marks: list[str] | None = None) -> GameRecord | None:
        cached = self.cache.get_game(appid)
        if cached and cached.get("language") == STEAM_STORE_LANGUAGE and cached.get("cache_version") == GAME_RECORD_CACHE_VERSION:
            cached["source_marks"] = sorted(set(cached.get("source_marks", []) + (source_marks or [])))
            return GameRecord(**cached)
        return None

    async def app_details(
        self,
        appid: int,
        source_marks: list[str] | None = None,
        tag_weights: dict[str, int] | None = None,
    ) -> GameRecord | None:
        cached = self._cached_record(appid, source_marks)
        if cached:
            return cached
        if self.cache.get_http(f"appdetails_miss:{appid}", max_age=STEAM_MISS_TTL_SECONDS):
            return None

        detail_url = f"{STEAM_STORE_BASE}/api/appdetails"
        review_url = f"{STEAM_STORE_BASE}/appreviews/{appid}"
        detail_task = asyncio.to_thread(
            _get_json,
            detail_url,
            {"appids": appid, "filters": "basic,categories,genres,release_date,price_overview", "l": STEAM_STORE_LANGUAGE, "cc": "cn"},
        )
        review_task = asyncio.to_thread(
            _get_json,
            review_url,
            {"json": 1, "filter": "recent", "language": "all", "purchase_type": "all", "num_per_page": 0},
        )
        detail_response, review_response = await asyncio.gather(detail_task, review_task, return_exceptions=True)

        if isinstance(detail_response, Exception):
            self.cache.put_http(f"appdetails_miss:{appid}", {"miss": True})
            return None
        detail_body = detail_response.get(str(appid), {})
        if not detail_body.get("success"):
            self.cache.put_http(f"appdetails_miss:{appid}", {"miss": True})
            return None
        data = detail_body.get("data", {})
        if data.get("type") != "game":
            self.cache.put_http(f"appdetails_miss:{appid}", {"miss": True})
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

        price = data.get("price_overview") or {}
        price_final = 0 if data.get("is_free") else price.get("final")
        price_lowest = None
        if price_final is not None:
            stored = self.cache.get_http(f"price_low:{appid}", max_age=None)
            price_lowest = price_final if stored is None else min(int(stored["low"]), int(price_final))
            if stored is None or price_lowest < int(stored["low"]):
                self.cache.put_http(f"price_low:{appid}", {"low": price_lowest})

        record = GameRecord(
            appid=appid,
            name=display_name(appid, data.get("name", f"App {appid}")),
            tags=tags,
            categories=category_names,
            genres=genre_names,
            tag_weights=tag_weights or {},
            price_final=price_final,
            price_initial=price.get("initial"),
            price_discount=price.get("discount_percent"),
            price_currency="CNY" if data.get("is_free") else price.get("currency"),
            price_lowest=price_lowest,
            release_date=(data.get("release_date") or {}).get("date"),
            coming_soon=bool((data.get("release_date") or {}).get("coming_soon", False)),
            review_percent=review_percent,
            review_count=review_count,
            capsule_image=data.get("header_image") or data.get("capsule_image"),
            store_url=f"{STEAM_STORE_BASE}/app/{appid}",
            source_marks=source_marks or [],
            max_players_hint=_max_players_hint(category_names),
            language=STEAM_STORE_LANGUAGE,
            cache_version=GAME_RECORD_CACHE_VERSION,
        )
        self.cache.put_game(appid, record.to_dict())
        return record

    async def app_details_many(self, appids: Iterable[int], source_map: dict[int, list[str]] | None = None) -> list[GameRecord]:
        from .tags import fetch_tag_weights

        appid_list = list(appids)
        missing = [appid for appid in appid_list if self._cached_record(appid) is None]
        tag_map = await fetch_tag_weights(missing) if missing else {}
        sem = _steam_semaphore()

        async def fetch(appid: int) -> GameRecord | None:
            async with sem:
                return await self.app_details(appid, (source_map or {}).get(appid, []), tag_map.get(appid))

        records = await asyncio.gather(*(fetch(appid) for appid in appid_list))
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
    last_exc: Exception | None = None
    for attempt in range(3):
        request = Request(full_url, headers={"User-Agent": "steam-group-rec/0.1"})
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in (401, 403):
                raise PermissionError from exc
            if code in (429, 500, 502, 503) and attempt < 2:
                last_exc = exc
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last_exc  # pragma: no cover
