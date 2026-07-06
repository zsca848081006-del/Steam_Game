from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import CACHE_TTL_SECONDS, GAME_CACHE_DB


class GameCache:
    def __init__(self, db_path: Path = GAME_CACHE_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS game_records (
                    appid INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS steam_http_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL
                )
                """
            )

    def get_game(self, appid: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload, fetched_at FROM game_records WHERE appid = ?",
                (appid,),
            ).fetchone()
        if not row or int(time.time()) - row["fetched_at"] > CACHE_TTL_SECONDS:
            return None
        return json.loads(row["payload"])

    def put_game(self, appid: int, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO game_records(appid, payload, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    payload = excluded.payload,
                    fetched_at = excluded.fetched_at
                """,
                (appid, json.dumps(payload, ensure_ascii=False), int(time.time())),
            )

