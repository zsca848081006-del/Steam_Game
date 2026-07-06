from __future__ import annotations

import asyncio
import re
import time
from datetime import date

from .cache import GameCache
from .config import CANDIDATE_POOL_TTL_SECONDS, INGEST_RECENT_MONTHS, STEAM_STORE_BASE
from .steam_api import _get_json


POOL_CACHE_KEY = "candidate_pool_v1"

# Steam search 的多个 category3 是“与”关系，所以按合作(9)和多人(1)分别查询后合并。
SEARCH_CATEGORY_IDS = (9, 1)

RECENT_HOT_LIMIT = 50
HIGH_RATED_LIMIT = 40
EVERGREEN_LIMIT = 15
FRESH_LIMIT = 25

_ROW = re.compile(r'<a[^>]*data-ds-appid="(\d+)"[^>]*>(.*?)</a>', re.S)
_TITLE = re.compile(r'<span class="title">([^<]+)</span>')
_RELEASED = re.compile(r"search_released[^>]*>\s*(?:<[^>]+>\s*)*([^<]*?)\s*<")
_REVIEW_TOOLTIP = re.compile(r'data-tooltip-html="([^"]*)"')
_REVIEW_COUNT = re.compile(r"([\d,]+)\s*篇用户评测")
_REVIEW_PERCENT = re.compile(r"(\d+)%\s*为好评")
_RELEASE_YEAR_MONTH = re.compile(r"(\d{4})\s*年(?:\s*(\d{1,2})\s*月)?")
_FRESH_SKIP = re.compile(r"demo|playtest|试玩|测试", re.I)


class SearchItem:
    def __init__(self, appid: int, name: str, released: str, review_percent: int | None, review_count: int | None) -> None:
        self.appid = appid
        self.name = name
        self.released = released
        self.review_percent = review_percent
        self.review_count = review_count

    def released_within_months(self, months: int) -> bool:
        match = _RELEASE_YEAR_MONTH.search(self.released)
        if not match:
            return False
        year = int(match.group(1))
        month = int(match.group(2) or 6)
        today = date.today()
        return (today.year - year) * 12 + (today.month - month) <= months


async def load_candidate_pools(cache: GameCache) -> tuple[dict[int, list[str]], dict[int, list[str]], str]:
    """返回 (动态主候选, 动态尝鲜候选, 状态说明)；失败时回退陈旧缓存或空池。"""
    cached = cache.get_http(POOL_CACHE_KEY, max_age=CANDIDATE_POOL_TTL_SECONDS)
    if cached:
        return _decode_pool(cached["main"]), _decode_pool(cached["fresh"]), "候选池来自缓存。"

    try:
        main, fresh = await asyncio.to_thread(_build_pools)
        cache.put_http(POOL_CACHE_KEY, {"main": _encode_pool(main), "fresh": _encode_pool(fresh)})
        return main, fresh, f"候选池已刷新：主线 {len(main)} 个，尝鲜 {len(fresh)} 个。"
    except Exception as exc:
        stale = cache.get_http(POOL_CACHE_KEY, max_age=None)
        if stale:
            return _decode_pool(stale["main"]), _decode_pool(stale["fresh"]), f"候选池刷新失败，使用陈旧缓存：{exc}"
        return {}, {}, f"候选池刷新失败，仅使用静态种子：{exc}"


def _build_pools() -> tuple[dict[int, list[str]], dict[int, list[str]]]:
    main: dict[int, list[str]] = {}
    fresh: dict[int, list[str]] = {}

    topseller_items: list[SearchItem] = []
    for category in SEARCH_CATEGORY_IDS:
        for start in (0, 100):
            topseller_items.extend(_search_page({"filter": "topsellers", "category3": category, "start": start}))
        time.sleep(0.3)

    recent_hot = [
        item
        for item in topseller_items
        if item.released_within_months(INGEST_RECENT_MONTHS) and (item.review_percent or 0) >= 70
    ]
    _add(main, recent_hot, RECENT_HOT_LIMIT, "Steam 近一年热门新品")
    _add(main, topseller_items, EVERGREEN_LIMIT, "Steam 热销多人")

    high_rated: list[SearchItem] = []
    for category in SEARCH_CATEGORY_IDS:
        high_rated.extend(
            item
            for item in _search_page({"sort_by": "Reviews_DESC", "hidef2p": 1, "category3": category})
            if (item.review_count or 0) >= 400 and (item.review_percent or 0) >= 85
        )
        time.sleep(0.3)
    _add(main, high_rated, HIGH_RATED_LIMIT, "Steam 高口碑多人")

    coming_soon: list[SearchItem] = []
    for category in SEARCH_CATEGORY_IDS:
        coming_soon.extend(
            item
            for item in _search_page({"filter": "comingsoon", "category3": category})
            if not _FRESH_SKIP.search(item.name)
        )
        time.sleep(0.3)
    for item in coming_soon:
        if len(fresh) >= FRESH_LIMIT:
            break
        if item.appid not in main and item.appid not in fresh:
            fresh[item.appid] = ["尝鲜档", "Steam 即将推出"]

    return main, fresh


def _add(pool: dict[int, list[str]], items: list[SearchItem], limit: int, mark: str) -> None:
    added = 0
    for item in items:
        if added >= limit:
            break
        existing = pool.get(item.appid)
        if existing is not None:
            if mark not in existing:
                existing.append(mark)
            continue
        pool[item.appid] = [mark]
        added += 1


def _search_page(extra: dict[str, object]) -> list[SearchItem]:
    params: dict[str, object] = {
        "start": 0,
        "count": 100,
        "infinite": 1,
        "json": 1,
        "l": "schinese",
        "cc": "CN",
        "category1": 998,
        **extra,
    }
    body = _get_json(f"{STEAM_STORE_BASE}/search/results/", params)
    return _parse_rows(body.get("results_html", ""))


def _parse_rows(html: str) -> list[SearchItem]:
    items: list[SearchItem] = []
    seen: set[int] = set()
    for match in _ROW.finditer(html):
        appid = int(match.group(1))
        if appid in seen:
            continue
        seen.add(appid)
        block = match.group(2)
        title = _TITLE.search(block)
        released = _RELEASED.search(block)
        tooltip = _REVIEW_TOOLTIP.search(block)
        review_percent = None
        review_count = None
        if tooltip:
            percent_match = _REVIEW_PERCENT.search(tooltip.group(1))
            count_match = _REVIEW_COUNT.search(tooltip.group(1))
            review_percent = int(percent_match.group(1)) if percent_match else None
            review_count = int(count_match.group(1).replace(",", "")) if count_match else None
        items.append(
            SearchItem(
                appid=appid,
                name=title.group(1).strip() if title else "",
                released=released.group(1).strip() if released else "",
                review_percent=review_percent,
                review_count=review_count,
            )
        )
    return items


def _encode_pool(pool: dict[int, list[str]]) -> dict[str, list[str]]:
    return {str(appid): marks for appid, marks in pool.items()}


def _decode_pool(pool: dict[str, list[str]]) -> dict[int, list[str]]:
    return {int(appid): marks for appid, marks in pool.items()}
