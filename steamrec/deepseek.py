from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.request import Request, urlopen

from .config import DEEPSEEK_API_BASE, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT_SECONDS
from .models import Recommendation


class AiResult:
    def __init__(self, recommendations: list[Recommendation], used: bool, status: str) -> None:
        self.recommendations = recommendations
        self.used = used
        self.status = status


async def refine_recommendations(
    recommendations: list[Recommendation],
    group_tags: list[tuple[str, float]],
    distribution: str,
    boost_tags: list[str],
    pass_tags: list[str],
) -> AiResult:
    if not recommendations:
        return AiResult(recommendations, False, "没有可供 AI 精排的候选。")
    if not DEEPSEEK_API_KEY:
        return AiResult(recommendations, False, "未配置 DeepSeek API key，使用算法排序。")

    payload = _build_payload(recommendations[:25], group_tags, distribution, boost_tags, pass_tags)
    try:
        raw = await asyncio.to_thread(_chat_completion, payload)
        refined = _apply_ai_result(recommendations, raw)
        return AiResult(refined, True, "DeepSeek 已参与精排和理由生成。")
    except Exception as exc:
        return AiResult(recommendations, False, f"DeepSeek 调用失败，已回退算法排序：{exc}")


def _build_payload(
    recommendations: list[Recommendation],
    group_tags: list[tuple[str, float]],
    distribution: str,
    boost_tags: list[str],
    pass_tags: list[str],
) -> dict[str, Any]:
    facts = {
        "group_tags": [{"tag": tag, "weight": round(value, 5)} for tag, value in group_tags[:12]],
        "distribution": distribution,
        "boost_tags": boost_tags,
        "pass_tags": pass_tags,
        "candidates": [
            {
                "appid": item.appid,
                "name": item.name,
                "algorithm_fit_percent": item.fit_percent,
                "tags": item.tags,
                "source_marks": item.source_marks,
                "review_score_10": item.review_percent,
                "review_count": item.review_count,
                "owned_by_count": len(item.owned_by),
                "deterministic_reason": item.reason,
            }
            for item in recommendations
        ],
    }
    system = (
        "你是 Steam 多人游戏推荐助手。你只能基于用户提供的 JSON 事实精排候选并写中文理由。"
        "严禁新增、删除或编造 appid；严禁引用 JSON 之外的事实；不确定时就少说。"
        "输出必须是纯 JSON，不要 Markdown。"
    )
    user = (
        "请对这些已经由结构化算法筛出的 Steam 多人游戏候选做精排。"
        "返回 JSON 对象，格式为 {\"items\":[{\"appid\":整数,\"fit_percent\":55到98的整数,"
        "\"reason\":\"一句中文推荐理由\"}]}。"
        "reason 必须使用这个句式：适合点：...；依据：...。"
        "适合点只能引用 group_tags、候选 tags、source_marks 或 owned_by_count；"
        "依据必须引用一个真实口碑、来源或拥有情况事实。"
        "只能使用输入 candidates 中已有 appid。事实如下：\n"
        + json.dumps(facts, ensure_ascii=False)
    )
    return {
        "model": DEEPSEEK_MODEL,
        "temperature": 0.2,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }


def _chat_completion(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{DEEPSEEK_API_BASE.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=DEEPSEEK_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def _apply_ai_result(recommendations: list[Recommendation], raw: dict[str, Any]) -> list[Recommendation]:
    by_appid = {item.appid: item for item in recommendations}
    refined: list[Recommendation] = []
    seen: set[int] = set()
    for item in raw.get("items", []):
        try:
            appid = int(item["appid"])
        except (KeyError, TypeError, ValueError):
            continue
        existing = by_appid.get(appid)
        if not existing or appid in seen:
            continue
        seen.add(appid)
        try:
            existing.fit_percent = max(55, min(98, int(item.get("fit_percent", existing.fit_percent))))
        except (TypeError, ValueError):
            pass
        reason = str(item.get("reason", "")).strip()
        if reason:
            existing.reason = reason
        refined.append(existing)

    refined.extend(item for item in recommendations if item.appid not in seen)
    return refined[:20]
