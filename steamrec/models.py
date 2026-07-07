from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RecommendRequest:
    steam_api_key: str
    steam_ids: list[str]
    deepseek_api_key: str = ""
    include_fresh: bool = False
    exclude_owned: bool = True
    required_players: int | None = None
    boost_tags: list[str] = field(default_factory=list)
    pass_tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RecommendRequest":
        steam_ids = [str(item).strip() for item in payload.get("steam_ids", []) if str(item).strip()]
        if not payload.get("steam_api_key") or not steam_ids:
            raise ValueError("steam_api_key and steam_ids are required")
        if len(steam_ids) > 16:
            raise ValueError("steam_ids supports at most 16 players")
        required_players = payload.get("required_players")
        if required_players in ("", 0):
            required_players = None
        if required_players is not None:
            required_players = int(required_players)
            if required_players < 2 or required_players > 16:
                raise ValueError("required_players must be between 2 and 16")
        return cls(
            steam_api_key=str(payload["steam_api_key"]),
            steam_ids=steam_ids,
            deepseek_api_key=str(payload.get("deepseek_api_key", "")).strip(),
            include_fresh=bool(payload.get("include_fresh", False)),
            exclude_owned=bool(payload.get("exclude_owned", True)),
            required_players=required_players,
            boost_tags=[str(item).strip() for item in payload.get("boost_tags", []) if str(item).strip()],
            pass_tags=[str(item).strip() for item in payload.get("pass_tags", []) if str(item).strip()],
        )


@dataclass
class OwnedGame:
    appid: int
    name: str = ""
    playtime_forever: int = 0
    playtime_2weeks: int = 0


@dataclass
class PlayerProfile:
    steamid: str
    games: list[OwnedGame]
    valid: bool = True
    reason: str | None = None
    persona_name: str | None = None


@dataclass
class GameRecord:
    appid: int
    name: str
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    # 玩家投票标签 {tagid(str): 票数}；JSON round-trip 需要字符串键，展示名按请求语言另行解析。
    tag_weights: dict[str, int] = field(default_factory=dict)
    release_date: str | None = None
    coming_soon: bool = False
    review_percent: int | None = None
    review_count: int | None = None
    capsule_image: str | None = None
    store_url: str = ""
    source_marks: list[str] = field(default_factory=list)
    max_players_hint: int | None = None
    language: str = ""
    cache_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    appid: int
    name: str
    score: float
    fit_percent: int
    store_url: str
    tags: list[str]
    source_marks: list[str]
    reason: str
    capsule_image: str | None = None
    review_percent: int | None = None
    review_count: int | None = None
    owned_by: list[str] = field(default_factory=list)


@dataclass
class RecommendResponse:
    valid_players: list[PlayerProfile]
    excluded_players: list[PlayerProfile]
    group_tags: list[tuple[str, float]]
    distribution: str
    recommendations: list[Recommendation]
    fresh_recommendations: list[Recommendation] = field(default_factory=list)
    ai_used: bool = False
    ai_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
