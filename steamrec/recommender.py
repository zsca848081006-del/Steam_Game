from __future__ import annotations

import math
from collections import Counter, defaultdict

from .candidates import FRESH_CANDIDATES, MAIN_CANDIDATES
from .models import GameRecord, PlayerProfile, Recommendation
from .steam_api import is_multiplayer


def build_group_taste(players: list[PlayerProfile], owned_records: dict[int, GameRecord]) -> tuple[dict[str, float], str]:
    normalized_people: list[dict[str, float]] = []
    for player in players:
        weights: Counter[str] = Counter()
        for game in player.games:
            record = owned_records.get(game.appid)
            if not record or game.playtime_forever <= 0:
                continue
            signal = math.sqrt(game.playtime_forever)
            for tag in record.tags[:16]:
                weights[tag] += signal
        total = sum(weights.values())
        if total:
            normalized_people.append({tag: value / total for tag, value in weights.items()})

    group: defaultdict[str, float] = defaultdict(float)
    if not normalized_people:
        return {}, "insufficient"

    for person in normalized_people:
        for tag, value in person.items():
            group[tag] += value / len(normalized_people)

    values = sorted(group.values(), reverse=True)
    if not values:
        distribution = "insufficient"
    elif len(values) == 1 or values[0] > sum(values[1:6]) * 0.7:
        distribution = "focused"
    elif len(values) >= 4 and values[0] / max(values[3], 0.0001) < 1.8:
        distribution = "diverse"
    else:
        distribution = "mixed"
    return dict(group), distribution


def score_candidates(
    records: list[GameRecord],
    group_tags: dict[str, float],
    players: list[PlayerProfile],
    boost_tags: list[str],
    pass_tags: list[str],
    required_players: int | None = None,
) -> list[Recommendation]:
    owned_by_app: dict[int, list[str]] = defaultdict(list)
    for player in players:
        for game in player.games:
            owned_by_app[game.appid].append(player.steamid)

    boost = {tag.lower() for tag in boost_tags}
    passed = {tag.lower() for tag in pass_tags}
    recommendations: list[Recommendation] = []

    for record in records:
        if not is_multiplayer(record):
            continue
        if required_players and record.max_players_hint and record.max_players_hint < required_players:
            continue

        owned_by = owned_by_app.get(record.appid, [])
        if len(owned_by) == len(players):
            continue

        tag_score = 0.0
        matched_tags: list[str] = []
        for tag in record.tags:
            base = group_tags.get(tag, 0.0)
            lowered = tag.lower()
            if lowered in boost:
                base *= 2.5
            if lowered in passed:
                base *= 0.15
            if base:
                matched_tags.append(tag)
            tag_score += base

        multi_match_bonus = 1.0 + min(len(matched_tags), 4) * 0.12
        quality = _quality_score(record)
        ownership_bonus = 0.08 if owned_by else 0.0
        source_bonus = 0.03 * len(record.source_marks)
        score = tag_score * multi_match_bonus + quality + ownership_bonus + source_bonus
        if score <= 0:
            continue

        recommendations.append(
            Recommendation(
                appid=record.appid,
                name=record.name,
                score=round(score, 5),
                store_url=record.store_url,
                capsule_image=record.capsule_image,
                tags=record.tags[:8],
                source_marks=record.source_marks,
                review_percent=record.review_percent,
                review_count=record.review_count,
                owned_by=owned_by,
                reason=_reason(record, matched_tags, owned_by, len(players)),
            )
        )

    recommendations.sort(key=lambda item: item.score, reverse=True)
    return recommendations[:20]


def candidate_source_map(include_fresh: bool = False) -> dict[int, list[str]]:
    source_map = dict(MAIN_CANDIDATES)
    if include_fresh:
        source_map.update(FRESH_CANDIDATES)
    return source_map


def owned_appids(players: list[PlayerProfile], limit_per_player: int = 30) -> list[int]:
    appids: set[int] = set()
    for player in players:
        top_games = sorted(player.games, key=lambda game: game.playtime_forever, reverse=True)[:limit_per_player]
        appids.update(game.appid for game in top_games)
    return list(appids)


def _quality_score(record: GameRecord) -> float:
    if record.coming_soon:
        return 0.02
    if record.review_percent is None or record.review_count is None:
        return 0.0
    confidence = min(math.log10(max(record.review_count, 1)) / 5, 1)
    return (record.review_percent / 100) * confidence * 0.2


def _reason(record: GameRecord, matched_tags: list[str], owned_by: list[str], player_count: int) -> str:
    parts: list[str] = []
    if matched_tags:
        parts.append("命中这桌共同偏好的 " + " / ".join(matched_tags[:3]))
    if record.review_percent and record.review_count:
        parts.append(f"近期 Steam 评价信号 {record.review_percent}/10，样本 {record.review_count} 条")
    if record.source_marks:
        parts.append("候选来源：" + "、".join(record.source_marks[:2]))
    if owned_by:
        parts.append(f"已有 {len(owned_by)}/{player_count} 人拥有，适合补票开黑")
    else:
        parts.append("这桌库存并集中尚未出现")
    return "；".join(parts) + "。"
