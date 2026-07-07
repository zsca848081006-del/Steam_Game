from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import ANALYTICS_DB, STATS_TZ_OFFSET_HOURS


class Analytics:
    def __init__(self, db_path: Path = ANALYTICS_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    visitor TEXT,
                    ip TEXT,
                    meta TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def log(self, event: str, visitor: str, ip: str, meta: dict[str, Any] | None = None) -> None:
        # 埋点失败绝不能影响正常请求。
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO events(ts, event, visitor, ip, meta) VALUES (?, ?, ?, ?, ?)",
                    (int(time.time()), event, visitor, ip, json.dumps(meta or {}, ensure_ascii=False)),
                )
        except Exception:
            pass

    def summary(self, days: int = 30) -> dict[str, Any]:
        day_expr = f"date(ts, 'unixepoch', '{STATS_TZ_OFFSET_HOURS:+d} hours')"
        since = int(time.time()) - days * 86400
        with self._connect() as conn:
            totals = conn.execute(
                """
                SELECT
                    SUM(event = 'page_view') AS page_views,
                    SUM(event = 'recommend') AS recommends,
                    SUM(event = 'recommend' AND meta LIKE '%"status": "ok"%') AS recommend_ok,
                    COUNT(DISTINCT visitor) AS unique_visitors
                FROM events
                """
            ).fetchone()
            daily = conn.execute(
                f"""
                SELECT
                    {day_expr} AS day,
                    SUM(event = 'page_view') AS page_views,
                    COUNT(DISTINCT CASE WHEN event = 'page_view' THEN visitor END) AS unique_visitors,
                    SUM(event = 'recommend') AS recommends,
                    SUM(event = 'recommend' AND meta LIKE '%"status": "ok"%') AS recommend_ok
                FROM events
                WHERE ts >= ?
                GROUP BY day
                ORDER BY day DESC
                """,
                (since,),
            ).fetchall()
            recent = conn.execute(
                "SELECT ts, event, visitor, ip, meta FROM events ORDER BY id DESC LIMIT 20"
            ).fetchall()
        return {
            "totals": dict(totals),
            "daily": [dict(row) for row in daily],
            "recent": [dict(row) for row in recent],
        }
