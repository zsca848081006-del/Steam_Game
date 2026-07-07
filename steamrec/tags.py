from __future__ import annotations

import asyncio
import json

from .cache import GameCache
from .config import STEAM_API_BASE, STEAM_STORE_LANGUAGE, TAG_DICTIONARY_TTL_SECONDS


TAG_DICT_CACHE_KEY = f"tag_dictionary_{STEAM_STORE_LANGUAGE}_v1"
GETITEMS_BATCH_SIZE = 40


async def tag_dictionary(cache: GameCache) -> dict[int, str]:
    """tagid -> 请求语言标签名；失败时回退陈旧缓存或空表（空表时打分退化为 genre 逻辑）。"""
    cached = cache.get_http(TAG_DICT_CACHE_KEY, max_age=TAG_DICTIONARY_TTL_SECONDS)
    if cached:
        return {int(tagid): name for tagid, name in cached["tags"].items()}
    try:
        from .steam_api import _get_json

        body = await asyncio.to_thread(
            _get_json, f"{STEAM_API_BASE}/IStoreService/GetTagList/v1/", {"language": STEAM_STORE_LANGUAGE}
        )
        tags = {str(tag["tagid"]): tag["name"] for tag in body.get("response", {}).get("tags", []) if tag.get("name")}
        if tags:
            cache.put_http(TAG_DICT_CACHE_KEY, {"tags": tags})
            return {int(tagid): name for tagid, name in tags.items()}
    except Exception:
        pass
    stale = cache.get_http(TAG_DICT_CACHE_KEY, max_age=None)
    if stale:
        return {int(tagid): name for tagid, name in stale["tags"].items()}
    return {}


async def fetch_tag_weights(appids: list[int]) -> dict[int, dict[str, int]]:
    """批量拉每个游戏的玩家投票标签 {appid: {tagid(str): 票数}}；单批失败跳过，不阻塞主流程。"""
    from .steam_api import _get_json

    result: dict[int, dict[str, int]] = {}
    for start in range(0, len(appids), GETITEMS_BATCH_SIZE):
        chunk = appids[start : start + GETITEMS_BATCH_SIZE]
        input_json = json.dumps(
            {
                "ids": [{"appid": appid} for appid in chunk],
                "context": {"language": STEAM_STORE_LANGUAGE, "country_code": "CN"},
                "data_request": {"include_tag_count": True},
            }
        )
        try:
            body = await asyncio.to_thread(
                _get_json, f"{STEAM_API_BASE}/IStoreBrowseService/GetItems/v1/", {"input_json": input_json}
            )
        except Exception:
            continue
        for item in body.get("response", {}).get("store_items", []):
            if item.get("success") == 1 and item.get("appid"):
                result[int(item["appid"])] = {
                    str(tag["tagid"]): int(tag.get("weight", 1)) for tag in item.get("tags", []) if tag.get("tagid")
                }
    return result
