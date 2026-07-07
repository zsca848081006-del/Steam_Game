from __future__ import annotations

import math
from collections import Counter, defaultdict

from .awards import TGA_MULTIPLAYER_MARKS
from .candidates import FRESH_CANDIDATES, MAIN_CANDIDATES
from .models import GameRecord, PlayerProfile, Recommendation
from .steam_api import NOISE_TAGS, is_multiplayer
from .tag_aliases import expand_user_terms, term_matches


# 近两周时长的放大倍数：让"最近在玩"主导口味，而不是被多年累计时长绑架。
RECENT_PLAYTIME_MULTIPLIER = 25

# 余弦相似度达到该值即视为满分匹配（fit 98%），用于推荐度的绝对标定。
FIT_COSINE_CAP = 0.55


def _record_shares(record: GameRecord) -> dict[str, float]:
    """游戏的标签分布。键：投票标签用 str(tagid)，genre 回退用名字本身。"""
    if record.tag_weights:
        total = sum(record.tag_weights.values())
        if total > 0:
            return {key: weight / total for key, weight in record.tag_weights.items()}
    tags = record.tags[:8]
    if not tags:
        return {}
    return {tag: 1 / len(tags) for tag in tags}


def resolve_tag_name(key: str, tag_names: dict[int, str]) -> str:
    if key.isdigit():
        return tag_names.get(int(key), f"tag{key}")
    return key


def apply_display_tags(records: list[GameRecord], tag_names: dict[int, str]) -> None:
    """把投票标签解析成当前语言的展示名写回 record.tags(UI/DeepSeek/口味证据共用)。"""
    for record in records:
        if not record.tag_weights or not tag_names:
            continue
        ordered = sorted(record.tag_weights.items(), key=lambda item: item[1], reverse=True)
        names = []
        for key, _ in ordered:
            name = resolve_tag_name(key, tag_names)
            if name.lower() in NOISE_TAGS or name.startswith("tag"):
                continue
            names.append(name)
        if names:
            record.tags = names[:12]


def build_group_taste(players: list[PlayerProfile], owned_records: dict[int, GameRecord]) -> tuple[dict[str, float], str]:
    normalized_people: list[dict[str, float]] = []
    for player in players:
        weights: defaultdict[str, float] = defaultdict(float)
        for game in player.games:
            record = owned_records.get(game.appid)
            if not record or game.playtime_forever <= 0:
                continue
            signal = math.sqrt(game.playtime_forever + RECENT_PLAYTIME_MULTIPLIER * game.playtime_2weeks)
            for key, share in _record_shares(record).items():
                weights[key] += signal * share
        total = sum(weights.values())
        if total:
            normalized_people.append({key: value / total for key, value in weights.items()})

    group: defaultdict[str, float] = defaultdict(float)
    if not normalized_people:
        return {}, "insufficient"

    for person in normalized_people:
        for key, value in person.items():
            group[key] += value / len(normalized_people)

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


def top_group_tags(group: dict[str, float], tag_names: dict[int, str], limit: int = 20) -> list[tuple[str, float]]:
    """展示/证据用的群体口味标签：解析名字、滤噪声、重新归一。"""
    named: list[tuple[str, float]] = []
    for key, value in sorted(group.items(), key=lambda item: item[1], reverse=True):
        name = resolve_tag_name(key, tag_names)
        if name.lower() in NOISE_TAGS or name.startswith("tag"):
            continue
        named.append((name, value))
        if len(named) >= limit:
            break
    total = sum(value for _, value in named)
    if total <= 0:
        return []
    return [(name, value / total) for name, value in named]


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


def _tag_idf(records: list[GameRecord]) -> dict[str, float]:
    """按候选池文档频率降权烂大街标签：出现在所有候选里的标签权重归零。"""
    df: Counter[str] = Counter()
    for record in records:
        df.update(_record_shares(record).keys())
    n = max(len(records), 1)
    return {key: math.log(n / count) for key, count in df.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b[key] for key, value in a.items() if key in b)
    if dot <= 0:
        return 0.0
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


def score_candidates(
    records: list[GameRecord],
    group_tags: dict[str, float],
    players: list[PlayerProfile],
    boost_tags: list[str],
    pass_tags: list[str],
    required_players: int | None = None,
    exclude_owned: bool = True,
    tag_names: dict[int, str] | None = None,
) -> list[Recommendation]:
    tag_names = tag_names or {}
    owned_by_app: dict[int, list[str]] = defaultdict(list)
    for player in players:
        for game in player.games:
            owned_by_app[game.appid].append(player.steamid)

    boost = expand_user_terms(boost_tags)
    passed = expand_user_terms(pass_tags)
    idf = _tag_idf(records)
    group_vector = {key: value * idf.get(key, 0.0) for key, value in group_tags.items()}
    recommendations: list[Recommendation] = []

    for record in records:
        if not is_multiplayer(record):
            continue
        if required_players and record.max_players_hint and record.max_players_hint < required_players:
            continue

        owned_by = owned_by_app.get(record.appid, [])
        if exclude_owned and owned_by:
            continue
        if len(owned_by) == len(players):
            continue

        shares = _record_shares(record)
        share_names = {key: resolve_tag_name(key, tag_names) for key in shares}
        if boost or passed:
            adjusted = {}
            for key, share in shares.items():
                if boost and term_matches(share_names[key], boost):
                    share *= 2.5
                if passed and term_matches(share_names[key], passed):
                    share *= 0.15
                adjusted[key] = share
            shares = adjusted

        candidate_vector = {key: share * idf.get(key, 0.0) for key, share in shares.items()}
        similarity = _cosine(group_vector, candidate_vector)

        matched = sorted(
            (
                (group_vector[key] * candidate_vector[key], share_names[key])
                for key in candidate_vector
                if key in group_vector and group_vector[key] * candidate_vector[key] > 0
            ),
            reverse=True,
        )
        matched_tags = [name for _, name in matched if name.lower() not in NOISE_TAGS][:4]

        searchable_terms = list(share_names.values()) + record.source_marks + record.categories
        boost_match = bool(boost and any(term_matches(value, boost) for value in searchable_terms))
        pass_match = bool(passed and any(term_matches(value, passed) for value in searchable_terms))

        score = similarity * (1 + 0.08 * min(len(matched_tags), 4))
        if boost_match:
            score += 0.1
        if pass_match and not boost_match:
            score *= 0.35
        score += _quality_score(record)
        score += 0.05 if owned_by else 0.0
        score += 0.02 * len(record.source_marks)
        score *= _mainstream_factor(record)
        if any("新品" in mark or "即将推出" in mark for mark in record.source_marks):
            score += 0.03
        if score <= 0:
            continue

        recommendations.append(
            Recommendation(
                appid=record.appid,
                name=record.name,
                score=round(score, 5),
                fit_percent=_fit_percent(similarity),
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
    if record.review_count >= 500_000:
        return 0.55
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


def _fit_percent(similarity: float) -> int:
    # 绝对标定：整体不匹配时不再有人虚标 98%。
    return max(55, min(98, round(55 + 43 * min(similarity / FIT_COSINE_CAP, 1.0))))


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
