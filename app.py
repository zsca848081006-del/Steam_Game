from __future__ import annotations

import asyncio
import concurrent.futures
import hmac
import html
import json
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from steamrec.analytics import Analytics
from steamrec.config import (
    APP_HOST,
    APP_PORT,
    BASE_DIR,
    GAME_RECORD_CACHE_VERSION,
    MAX_CONCURRENT_RECOMMENDATIONS,
    RECOMMENDATION_TIMEOUT_SECONDS,
    STATS_TOKEN,
    STATS_TZ_OFFSET_HOURS,
    STEAM_STORE_LANGUAGE,
)
from steamrec.deepseek import refine_recommendations
from steamrec.ingest import load_candidate_pools
from steamrec.models import RecommendRequest, RecommendResponse
from steamrec.recommender import build_group_taste, build_taste_evidence, candidate_source_map, owned_appids, score_candidates
from steamrec.steam_api import SteamClient


STATIC_DIR = BASE_DIR / "static"

# 单一共享事件循环：所有推荐请求的协程都提交到这里，
# 让 steam_api/ingest 里的全局信号量和单飞锁真正跨请求生效，也避免每个请求各建一套线程池。
_LOOP = asyncio.new_event_loop()
# 默认执行器按 CPU 数定容(2 核机器只有 6 线程)，撑不起全局 Steam 并发 + DeepSeek 阻塞调用，固定放大。
_LOOP.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=32, thread_name_prefix="steamrec-io"))
threading.Thread(target=_LOOP.run_forever, name="steamrec-loop", daemon=True).start()

# 背压：同时计算的推荐请求上限，超出直接返回 503，不排队占线程。
_RECOMMEND_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_RECOMMENDATIONS)

_ANALYTICS = Analytics()


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "SteamGroupRec/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(
                {
                    "status": "ok",
                    "cache_version": GAME_RECORD_CACHE_VERSION,
                    "store_language": STEAM_STORE_LANGUAGE,
                    "ai_key_mode": "per_request",
                }
            )
            return
        if self.path == "/" or self.path.startswith("/?"):
            visitor, is_new = self._visitor()
            _ANALYTICS.log("page_view", visitor, self._client_ip())
            cookie_header = None
            if is_new:
                cookie_header = {"Set-Cookie": f"srvid={visitor}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax"}
            self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8", cookie_header)
            return
        if self.path.startswith("/static/"):
            relative = self.path.removeprefix("/static/").split("?", 1)[0]
            self._file(STATIC_DIR / relative, _content_type(relative))
            return
        if self.path.startswith("/stats"):
            self._stats()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/recommend":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        visitor, _ = self._visitor()
        started = time.time()
        status = "error"
        player_count = 0

        def track() -> None:
            _ANALYTICS.log(
                "recommend",
                visitor,
                self._client_ip(),
                {"status": status, "duration_ms": int((time.time() - started) * 1000), "players": player_count},
            )

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            request = RecommendRequest.from_dict(payload)
            player_count = len(request.steam_ids)
        except ValueError as exc:
            status = "bad_request"
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            track()
            return

        if not _RECOMMEND_SLOTS.acquire(blocking=False):
            status = "busy"
            self._json(
                {"detail": "服务器繁忙：同时计算的推荐请求已达上限，请稍后重试。"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            track()
            return
        try:
            future = asyncio.run_coroutine_threadsafe(run_recommendation(request), _LOOP)
            try:
                response = future.result(timeout=RECOMMENDATION_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                future.cancel()
                status = "timeout"
                self._json({"detail": "推荐计算超时，请稍后重试。"}, HTTPStatus.GATEWAY_TIMEOUT)
                return
            status = "ok"
            self._json(response.to_dict())
        except ValueError as exc:
            status = "bad_request"
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
        except RecommendationError as exc:
            status = "unprocessable"
            self._json({"detail": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)
        except Exception as exc:
            status = "error"
            self._json({"detail": f"internal error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            _RECOMMEND_SLOTS.release()
            track()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str, extra_headers: dict[str, str] | None = None) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _visitor(self) -> tuple[str, bool]:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("srvid")
        if morsel and morsel.value:
            return morsel.value[:64], False
        return uuid.uuid4().hex, True

    def _client_ip(self) -> str:
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def _stats(self) -> None:
        token = ""
        if "?" in self.path:
            for pair in self.path.split("?", 1)[1].split("&"):
                if pair.startswith("token="):
                    token = pair.removeprefix("token=")
        if not STATS_TOKEN or not hmac.compare_digest(token, STATS_TOKEN):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = _render_stats(_ANALYTICS.summary()).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
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

        dynamic_main, dynamic_fresh, pool_status = await load_candidate_pools(client.cache)
        print(f"candidate pool: {pool_status}")
        source_map, fresh_ids = candidate_source_map(
            include_fresh=payload.include_fresh,
            dynamic_main=dynamic_main,
            dynamic_fresh=dynamic_fresh,
        )
        candidate_records = await client.app_details_many(source_map.keys(), source_map)
        main_records = [record for record in candidate_records if record.appid not in fresh_ids]
        fresh_records = [record for record in candidate_records if record.appid in fresh_ids]

        recommendations = score_candidates(
            main_records,
            group_tags,
            valid_players,
            payload.boost_tags,
            payload.pass_tags,
            payload.required_players,
            payload.exclude_owned,
        )
        fresh_recommendations = (
            score_candidates(
                fresh_records,
                group_tags,
                valid_players,
                payload.boost_tags,
                payload.pass_tags,
                payload.required_players,
                payload.exclude_owned,
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
            payload.deepseek_api_key,
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
                payload.deepseek_api_key,
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


def _render_stats(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    tz = timezone(timedelta(hours=STATS_TZ_OFFSET_HOURS))

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else 0))

    daily_rows = "".join(
        f"<tr><td>{esc(row['day'])}</td><td>{esc(row['page_views'])}</td><td>{esc(row['unique_visitors'])}</td>"
        f"<td>{esc(row['recommends'])}</td><td>{esc(row['recommend_ok'])}</td></tr>"
        for row in summary["daily"]
    )
    recent_rows = "".join(
        f"<tr><td>{datetime.fromtimestamp(row['ts'], tz).strftime('%m-%d %H:%M:%S')}</td>"
        f"<td>{esc(row['event'])}</td><td>{esc((row['visitor'] or '-')[:8])}</td>"
        f"<td>{esc(row['ip'] or '-')}</td><td>{esc(row['meta'] or '')}</td></tr>"
        for row in summary["recent"]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<title>访问统计</title>
<style>
body {{ background: #0d1117; color: #d8dee9; font: 14px/1.6 system-ui, sans-serif; max-width: 880px; margin: 24px auto; padding: 0 16px; }}
h1, h2 {{ color: #7ce0d3; font-size: 18px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
th, td {{ border: 1px solid #2b3440; padding: 6px 10px; text-align: left; word-break: break-all; }}
th {{ background: #161c26; }}
.cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
.card {{ background: #161c26; border: 1px solid #2b3440; border-radius: 8px; padding: 12px 18px; }}
.card b {{ display: block; font-size: 22px; color: #7ce0d3; }}
</style></head><body>
<h1>Steam 群体推荐 · 访问统计</h1>
<div class="cards">
<div class="card"><b>{esc(totals['page_views'])}</b>页面访问</div>
<div class="card"><b>{esc(totals['unique_visitors'])}</b>独立访客(cookie)</div>
<div class="card"><b>{esc(totals['recommends'])}</b>推荐执行</div>
<div class="card"><b>{esc(totals['recommend_ok'])}</b>推荐成功</div>
</div>
<h2>最近 30 天(UTC{STATS_TZ_OFFSET_HOURS:+d})</h2>
<table><tr><th>日期</th><th>页面访问</th><th>独立访客</th><th>推荐执行</th><th>推荐成功</th></tr>{daily_rows or '<tr><td colspan="5">暂无数据</td></tr>'}</table>
<h2>最近 20 条事件</h2>
<table><tr><th>时间</th><th>事件</th><th>访客</th><th>IP</th><th>详情</th></tr>{recent_rows or '<tr><td colspan="5">暂无数据</td></tr>'}</table>
</body></html>"""


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
