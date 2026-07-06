from __future__ import annotations

import math
from collections import Counter, defaultdict

from .awards import TGA_MULTIPLAYER_MARKS
from .candidates import FRESH_CANDIDATES, MAIN_CANDIDATES
from .models import GameRecord, PlayerProfile, Recommendation
from .steam_api import is_multiplayer
from .tag_aliases import expand_user_terms, term_matches


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


def build_taste_evidence(
    players: list[PlayerProfile],
    owned_records: dict[int, GameRecord],
    group_tags: list[tuple[str, float]],
) -> dict[str, object]:
    top_tag_names = [tag for tag, _ in group_tags[:12]]
    by_tag: dict[str, dict[str, object]] = {}
    top_games: Counter[int] = Counter()

    for player in players:
        for game in player.games:
            if game.playtime_forever <= 0:
                continue
            record = owned_records.get(game.appid)
            if not record:
                continue
            top_games[game.appid] += game.playtime_forever
            for tag in record.tags:
                if tag not in top_tag_names:
                    continue
                entry = by_tag.setdefault(tag, {"tag": tag, "total_minutes": 0, "player_ids": set(), "games": Counter()})
                entry["total_minutes"] = int(entry["total_minutes"]) + game.playtime_forever
                entry["player_ids"].add(player.steamid)
                entry["games"][game.appid] += game.playtime_forever

    tag_evidence: list[dict[str, object]] = []
    for tag, weight in group_tags[:12]:
        entry = by_tag.get(tag)
        if not entry:
            continue
        game_counter: Counter[int] = entry["games"]
        examples = [
            {
                "name": owned_records[appid].name,
                "hours": round(minutes / 60, 1),
            }
            for appid, minutes in game_counter.most_common(4)
            if appid in owned_records
        ]
        tag_evidence.append(
            {
                "tag": tag,
                "weight": round(weight, 5),
                "total_hours": round(int(entry["total_minutes"]) / 60, 1),
                "player_count": len(entry["player_ids"]),
                "examples": examples,
            }
        )

    overall_examples = [
        {"name": owned_records[appid].name, "hours": round(minutes / 60, 1)}
        for appid, minutes in top_games.most_common(8)
        if appid in owned_records
    ]
    return {"tag_evidence": tag_evidence, "top_played_games": overall_examples}


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

    boost = expand_user_terms(boost_tags)
    passed = expand_user_terms(pass_tags)
    recommendations: list[Recommendation] = []

    for record in records:
        if not is_multiplayer(record):
            continue
        if required_players and record.max_players_hint and record.max_players_hint < required_players:
            continue

        owned_by = owned_by_app.get(record.appid, [])
        if len(owned_by) == len(players):
            continue

        searchable_terms = record.tags + record.source_marks + record.categories
        boost_match = bool(boost and any(term_matches(value, boost) for value in searchable_terms))
        pass_match = bool(passed and any(term_matches(value, passed) for value in searchable_terms))

        tag_score = 0.0
        matched_tags: list[str] = []
        for tag in record.tags:
            base = group_tags.get(tag, 0.0)
            if boost and term_matches(tag, boost):
                base *= 2.5
            if passed and term_matches(tag, passed):
                base *= 0.15
            if base:
                matched_tags.append(tag)
            tag_score += base
        if boost_match:
            tag_score += 0.14
            matched_tags.extend(mark for mark in record.source_marks if term_matches(mark, boost))
        if pass_match and not boost_match:
            tag_score *= 0.35

        multi_match_bonus = 1.0 + min(len(matched_tags), 4) * 0.12
        quality = _quality_score(record)
        ownership_bonus = 0.08 if owned_by else 0.0
        source_bonus = 0.03 * len(record.source_marks)
        score = tag_score * multi_match_bonus + quality + ownership_bonus + source_bonus
        score *= _mainstream_factor(record)
        if any("新品" in mark or "即将推出" in mark for mark in record.source_marks):
            score += 0.05
        if score <= 0:
            continue

        recommendations.append(
            Recommendation(
                appid=record.appid,
                name=record.name,
                score=round(score, 5),
                fit_percent=0,
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
    _apply_fit_percent(recommendations)
    return recommendations[:20]


def candidate_source_map(
    include_fresh: bool = False,
    dynamic_main: dict[int, list[str]] | None = None,
    dynamic_fresh: dict[int, list[str]] | None = None,
) -> tuple[dict[int, list[str]], set[int]]:
    source_map = dict(MAIN_CANDIDATES)
    for appid, marks in TGA_MULTIPLAYER_MARKS.items():
        source_map[appid] = sorted(set(source_map.get(appid, []) + marks))
    for appid, marks in (dynamic_main or {}).items():
        source_map[appid] = sorted(set(source_map.get(appid, []) + marks))

    fresh_pool = dynamic_fresh or FRESH_CANDIDATES
    fresh_ids = {appid for appid in fresh_pool if appid not in source_map}
    if include_fresh:
        for appid in fresh_ids:
            source_map[appid] = list(fresh_pool[appid])
    return source_map, fresh_ids


def owned_appids(players: list[PlayerProfile], limit_per_player: int = 30) -> list[int]:
    appids: set[int] = set()
    for player in players:
        top_games = sorted(player.games, key=lambda game: game.playtime_forever, reverse=True)[:limit_per_player]
        appids.update(game.appid for game in top_games)
    return list(appids)


def _mainstream_factor(record: GameRecord) -> float:
    # 国民级大热门对开黑推荐几乎没有信息量，做温和降权，让中体量高口碑和新品有机会浮上来。
    if not record.review_count:
        return 1.0
    if record.review_count >= 200_000:
        return 0.7
    if record.review_count >= 80_000:
        return 0.85
    return 1.0


def _quality_score(record: GameRecord) -> float:
    if record.coming_soon:
        return 0.02
    if record.review_percent is None or record.review_count is None:
        return 0.0
    confidence = min(math.log10(max(record.review_count, 1)) / 5, 1)
    return (record.review_percent / 100) * confidence * 0.2


def _apply_fit_percent(recommendations: list[Recommendation]) -> None:
    if not recommendations:
        return
    scores = [item.score for item in recommendations]
    best = max(scores)
    worst = min(scores)
    spread = best - worst
    for item in recommendations:
        if spread <= 0.00001:
            item.fit_percent = 86
        else:
            relative = (item.score - worst) / spread
            item.fit_percent = max(55, min(98, round(55 + relative * 43)))


def _reason(record: GameRecord, matched_tags: list[str], owned_by: list[str], player_count: int) -> str:
    parts: list[str] = []
    if matched_tags:
        parts.append("适合点：和这桌的共同偏好重合在 " + "、".join(matched_tags[:3]))
    if record.review_percent and record.review_count:
        parts.append(f"近期口碑：Steam 近期评价 {record.review_percent}/10，样本 {record.review_count} 条")
    if record.source_marks:
        parts.append("入选原因：" + "、".join(record.source_marks[:2]))
    if owned_by:
        parts.append(f"拥有情况：已有 {len(owned_by)}/{player_count} 人拥有，剩下的人补票即可开黑")
    else:
        parts.append("拥有情况：这桌人的库存并集中还没人拥有")
    return "；".join(parts) + "。"
