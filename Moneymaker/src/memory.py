"""Persistent memory — SQLite-backed store for runs, ideas, and weights.

Tables
------
runs               — one row per pipeline execution
ideas              — every idea that passed the money filter
conversion_events  — payment / click / signup / reply events
weights            — single-row JSON blob of learned weights
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from src.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    signals_mined INTEGER DEFAULT 0,
    ideas_generated INTEGER DEFAULT 0,
    ideas_passed  INTEGER DEFAULT 0,
    plans_built   INTEGER DEFAULT 0,
    deployed_url  TEXT    DEFAULT '',
    total_revenue REAL    DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ideas (
    idea_id       TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    source        TEXT NOT NULL,
    problem       TEXT NOT NULL,
    target_user   TEXT NOT NULL,
    solution      TEXT NOT NULL,
    passed        INTEGER NOT NULL,
    score         REAL    NOT NULL,
    reject_reason TEXT    DEFAULT '',
    mvp_format    TEXT    DEFAULT '',
    deployed_url  TEXT    DEFAULT '',
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS conversion_events (
    event_id     TEXT PRIMARY KEY,
    tracking_id  TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    platform     TEXT NOT NULL,
    value        REAL DEFAULT 0.0,
    timestamp    TEXT NOT NULL,
    run_id       TEXT DEFAULT '',
    metadata     TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS weights (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def init_db(path: str | None = None) -> None:
    """Create all tables and apply pending column migrations."""
    db_path = Path(path or settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(_SCHEMA)
        # Idempotent column migration for existing databases
        try:
            await db.execute("ALTER TABLE ideas ADD COLUMN reject_reason TEXT DEFAULT ''")
        except Exception:
            pass  # column already exists
        await db.commit()


class Memory:
    """Async SQLite memory store."""

    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path or settings.db_path)

    @asynccontextmanager
    async def _conn(self):
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    async def start_run(self, run_id: str) -> None:
        async with self._conn() as db:
            await db.execute(
                "INSERT INTO runs (run_id, started_at) VALUES (?, ?)",
                (run_id, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()

    async def finish_run(self, run_id: str, **fields: int | float | str) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = [*fields.values(), datetime.now(timezone.utc).isoformat(), run_id]
        async with self._conn() as db:
            await db.execute(
                f"UPDATE runs SET {set_clause}, ended_at = ? WHERE run_id = ?",
                values,
            )
            await db.commit()

    # ------------------------------------------------------------------
    # Ideas
    # ------------------------------------------------------------------

    async def save_idea(
        self,
        *,
        run_id: str,
        source: str,
        problem: str,
        target_user: str,
        solution: str,
        passed: bool,
        score: float,
        reject_reason: str = "",
        mvp_format: str = "",
        deployed_url: str = "",
    ) -> str:
        idea_id = uuid.uuid4().hex
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO ideas
                   (idea_id, run_id, source, problem, target_user, solution,
                    passed, score, reject_reason, mvp_format, deployed_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    idea_id, run_id, source, problem, target_user, solution,
                    int(passed), score, reject_reason, mvp_format, deployed_url,
                ),
            )
            await db.commit()
        return idea_id

    async def idea_stats(self, last_n_runs: int = 30) -> list[dict]:
        """Return idea rows for the last *last_n_runs* runs."""
        async with self._conn() as db:
            cursor = await db.execute(
                """SELECT i.* FROM ideas i
                   JOIN (
                       SELECT run_id FROM runs
                       ORDER BY started_at DESC LIMIT ?
                   ) recent ON i.run_id = recent.run_id""",
                (last_n_runs,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Conversion events
    # ------------------------------------------------------------------

    async def save_conversion_event(
        self,
        *,
        tracking_id: str,
        event_type: str,
        platform: str,
        value: float = 0.0,
        run_id: str = "",
        metadata: dict | None = None,
    ) -> None:
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO conversion_events
                   (event_id, tracking_id, event_type, platform, value,
                    timestamp, run_id, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    uuid.uuid4().hex,
                    tracking_id,
                    event_type,
                    platform,
                    value,
                    datetime.now(timezone.utc).isoformat(),
                    run_id,
                    json.dumps(metadata or {}),
                ),
            )
            await db.commit()

    async def reject_reason_stats(self, last_n_runs: int = 30) -> dict[str, dict[str, int]]:
        """Return rejection counts grouped by source and reject_reason.

        Shape: { source: { reject_reason: count } }
        Used to detect which sources produce low-quality signals by rejection category.
        """
        async with self._conn() as db:
            cursor = await db.execute(
                """SELECT i.source, i.reject_reason, COUNT(*) AS cnt
                   FROM ideas i
                   JOIN (
                       SELECT run_id FROM runs
                       ORDER BY started_at DESC LIMIT ?
                   ) recent ON i.run_id = recent.run_id
                   WHERE i.passed = 0 AND i.reject_reason != ''
                   GROUP BY i.source, i.reject_reason""",
                (last_n_runs,),
            )
            rows = await cursor.fetchall()
        result: dict[str, dict[str, int]] = {}
        for row in rows:
            result.setdefault(row["source"], {})[row["reject_reason"]] = row["cnt"]
        return result

    async def revenue_by_format(self, last_n_runs: int = 30) -> dict[str, float]:
        """Return total payment value grouped by mvp_format."""
        async with self._conn() as db:
            cursor = await db.execute(
                """SELECT i.mvp_format, COALESCE(SUM(ce.value), 0) AS rev
                   FROM ideas i
                   LEFT JOIN conversion_events ce
                     ON ce.run_id = i.run_id AND ce.event_type = 'payment'
                   JOIN (
                       SELECT run_id FROM runs
                       ORDER BY started_at DESC LIMIT ?
                   ) recent ON i.run_id = recent.run_id
                   WHERE i.passed = 1 AND i.mvp_format != ''
                   GROUP BY i.mvp_format""",
                (last_n_runs,),
            )
            rows = await cursor.fetchall()
            return {r["mvp_format"]: r["rev"] for r in rows}

    # ------------------------------------------------------------------
    # Weights
    # ------------------------------------------------------------------

    async def load_weights(self) -> dict:
        async with self._conn() as db:
            cursor = await db.execute("SELECT data FROM weights WHERE id = 1")
            row = await cursor.fetchone()
            return json.loads(row["data"]) if row else {}

    async def save_weights(self, data: dict) -> None:
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO weights (id, data, updated_at) VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE
                   SET data = excluded.data, updated_at = excluded.updated_at""",
                (json.dumps(data), datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
