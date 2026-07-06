from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, is_dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from steamrec.candidates import FRESH_CANDIDATES
from steamrec.config import APP_HOST, APP_PORT, BASE_DIR, DEEPSEEK_API_KEY, GAME_RECORD_CACHE_VERSION, STEAM_STORE_LANGUAGE
from steamrec.deepseek import refine_recommendations
from steamrec.models import RecommendRequest, RecommendResponse
from steamrec.recommender import build_group_taste, build_taste_evidence, candidate_source_map, owned_appids, score_candidates
from steamrec.steam_api import SteamClient


STATIC_DIR = BASE_DIR / "static"


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "SteamGroupRec/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(
                {
                    "status": "ok",
                    "cache_version": GAME_RECORD_CACHE_VERSION,
                    "store_language": STEAM_STORE_LANGUAGE,
                    "ai_configured": bool(DEEPSEEK_API_KEY),
                }
            )
            return
        if self.path == "/" or self.path.startswith("/?"):
            self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path.startswith("/static/"):
            relative = self.path.removeprefix("/static/").split("?", 1)[0]
            self._file(STATIC_DIR / relative, _content_type(relative))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/recommend":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            request = RecommendRequest.from_dict(payload)
            response = asyncio.run(run_recommendation(request))
            self._json(response.to_dict())
        except ValueError as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
        except RecommendationError as exc:
            self._json({"detail": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)
        except Exception as exc:
            self._json({"detail": f"internal error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


async def run_recommendation(payload: RecommendRequest) -> RecommendResponse:
    client = SteamClient()
    try:
        raw_players = [
            await client.owned_games(payload.steam_api_key, steamid.strip())
            for steamid in payload.steam_ids
            if steamid.strip()
        ]
        valid_players = [player for player in raw_players if player.valid]
        excluded_players = [player for player in raw_players if not player.valid]
        if len(valid_players) < 2:
            raise RecommendationError("有效玩家少于 2 人，无法建模共同口味。")

        taste_appids = owned_appids(valid_players)
        owned_records_list = await client.app_details_many(taste_appids, {})
        owned_records = {record.appid: record for record in owned_records_list}
        group_tags, distribution = build_group_taste(valid_players, owned_records)
        if not group_tags:
            raise RecommendationError("有效库存时长不足，无法生成口味向量。")

        source_map = candidate_source_map(include_fresh=payload.include_fresh)
        candidate_records = await client.app_details_many(source_map.keys(), source_map)
        fresh_ids = set(FRESH_CANDIDATES)
        main_records = [record for record in candidate_records if record.appid not in fresh_ids]
        fresh_records = [record for record in candidate_records if record.appid in fresh_ids]

        recommendations = score_candidates(
            main_records,
            group_tags,
            valid_players,
            payload.boost_tags,
            payload.pass_tags,
            payload.required_players,
        )
        fresh_recommendations = (
            score_candidates(
                fresh_records,
                group_tags,
                valid_players,
                payload.boost_tags,
                payload.pass_tags,
                payload.required_players,
            )
            if payload.include_fresh
            else []
        )

        top_tags = sorted(group_tags.items(), key=lambda item: item[1], reverse=True)[:20]
        taste_evidence = build_taste_evidence(valid_players, owned_records, top_tags)
        ai_result = await refine_recommendations(
            recommendations,
            top_tags,
            distribution,
            payload.boost_tags,
            payload.pass_tags,
            taste_evidence,
        )
        recommendations = ai_result.recommendations

        fresh_ai_used = False
        fresh_ai_status = ""
        if fresh_recommendations:
            fresh_ai_result = await refine_recommendations(
                fresh_recommendations,
                top_tags,
                distribution,
                payload.boost_tags,
                payload.pass_tags,
                taste_evidence,
            )
            fresh_recommendations = fresh_ai_result.recommendations
            fresh_ai_used = fresh_ai_result.used
            fresh_ai_status = fresh_ai_result.status

        return RecommendResponse(
            valid_players=valid_players,
            excluded_players=excluded_players,
            group_tags=[(tag, round(value, 5)) for tag, value in top_tags],
            distribution=distribution,
            recommendations=recommendations,
            fresh_recommendations=fresh_recommendations,
            ai_used=ai_result.used or fresh_ai_used,
            ai_status=_merge_status(ai_result.status, fresh_ai_status),
        )
    finally:
        await client.close()


class RecommendationError(RuntimeError):
    pass


def _merge_status(*values: str) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            parts.append(cleaned)
    return " ".join(parts)


def _content_type(relative: str) -> str:
    if relative.endswith(".css"):
        return "text/css; charset=utf-8"
    if relative.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if relative.endswith(".html"):
        return "text/html; charset=utf-8"
    return "application/octet-stream"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), AppHandler)
    print(f"Steam group recommender running at http://{APP_HOST}:{APP_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
