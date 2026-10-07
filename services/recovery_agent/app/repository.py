"""PostgreSQL repository owned by the Recovery Agent service."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import asyncpg

from .assessment import RecoveryHistory
from .config import Settings
from .schemas import RecoveryCheckInCreate, RecoveryEvaluateResponse, SleepLogCreate


class RecoveryRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if not self.settings.DATABASE_URL:
            raise RuntimeError(
                "RECOVERY_DATABASE_URL is required for the Recovery Agent"
            )
        database_url = self.settings.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        self.pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        await self.ensure_schema()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    @property
    def _pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Recovery repository is not connected")
        return self.pool

    async def ensure_schema(self) -> None:
        schema = self.settings.validated_schema()
        async with self._pool.acquire() as conn:
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".sleep_logs (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL CHECK (user_id > 0),
                    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 0 AND 1440),
                    quality INTEGER NOT NULL CHECK (quality BETWEEN 1 AND 5),
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )'''
            )
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".recovery_checkins (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL CHECK (user_id > 0),
                    energy INTEGER NOT NULL CHECK (energy BETWEEN 1 AND 10),
                    soreness INTEGER NOT NULL CHECK (soreness BETWEEN 1 AND 10),
                    stress INTEGER NOT NULL CHECK (stress BETWEEN 1 AND 10),
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )'''
            )
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".recovery_assessments (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL CHECK (user_id > 0),
                    status VARCHAR(16) NOT NULL,
                    score INTEGER NOT NULL,
                    response JSONB NOT NULL,
                    tool_trace JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )'''
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_sleep_logs_user_created ON "{schema}".sleep_logs(user_id, created_at DESC)'
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_recovery_checkins_user_created ON "{schema}".recovery_checkins(user_id, created_at DESC)'
            )

    async def create_sleep_log(self, payload: SleepLogCreate) -> asyncpg.Record:
        schema = self.settings.validated_schema()
        return await self._pool.fetchrow(
            f'''INSERT INTO "{schema}".sleep_logs (user_id, duration_minutes, quality, notes)
                VALUES ($1, $2, $3, $4)
                RETURNING id, user_id, duration_minutes, quality, notes, created_at''',
            payload.user_id,
            payload.duration_minutes,
            payload.quality,
            payload.notes,
        )

    async def create_checkin(self, payload: RecoveryCheckInCreate) -> None:
        schema = self.settings.validated_schema()
        await self._pool.execute(
            f'''INSERT INTO "{schema}".recovery_checkins (user_id, energy, soreness, stress, notes)
                VALUES ($1, $2, $3, $4, $5)''',
            payload.user_id,
            payload.energy,
            payload.soreness,
            payload.stress,
            payload.notes,
        )

    async def get_history(self, user_id: int) -> RecoveryHistory:
        schema = self.settings.validated_schema()
        row = await self._pool.fetchrow(
            f'''SELECT
                    (SELECT COUNT(*) FROM "{schema}".sleep_logs WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '7 days') AS sleep_logs,
                    (SELECT AVG(duration_minutes) FROM "{schema}".sleep_logs WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '7 days') AS avg_sleep_minutes,
                    (SELECT AVG(quality) FROM "{schema}".sleep_logs WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '7 days') AS avg_sleep_quality,
                    (SELECT COUNT(*) FROM "{schema}".recovery_checkins WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '7 days') AS checkins''',
            user_id,
        )
        return RecoveryHistory(
            sleep_logs_last_7_days=int(row["sleep_logs"]),
            average_sleep_minutes=float(row["avg_sleep_minutes"])
            if row["avg_sleep_minutes"] is not None
            else None,
            average_sleep_quality=float(row["avg_sleep_quality"])
            if row["avg_sleep_quality"] is not None
            else None,
            check_ins_last_7_days=int(row["checkins"]),
            workouts_last_7_days=0,
        )

    async def save_assessment(
        self, user_id: int, assessment: RecoveryEvaluateResponse
    ) -> None:
        schema = self.settings.validated_schema()
        await self._pool.execute(
            f'''INSERT INTO "{schema}".recovery_assessments (user_id, status, score, response, tool_trace)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)''',
            user_id,
            assessment.status,
            assessment.score,
            assessment.model_dump_json(),
            json.dumps(assessment.tool_trace),
        )

    async def list_records(self, resource, page, page_size, user_id=None):
        table, _ = RECORD_COLUMNS[resource]
        schema = self.settings.validated_schema()
        condition = " WHERE user_id = $1" if user_id is not None else ""
        args = [user_id] if user_id is not None else []
        async with (
            self._pool.acquire() as conn,
            conn.transaction(isolation="repeatable_read", readonly=True),
        ):
            total = await conn.fetchval(
                f'SELECT COUNT(*) FROM "{schema}".{table}{condition}', *args
            )
            rows = await conn.fetch(
                f'SELECT * FROM "{schema}".{table}{condition} ORDER BY created_at DESC, id DESC LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}',
                *args,
                page_size,
                (page - 1) * page_size,
            )
        return {"items": [record_dict(row) for row in rows], "total": total}

    async def write_record(self, resource, values, record_id=None):
        table, columns = RECORD_COLUMNS[resource]
        schema = self.settings.validated_schema()
        args = [
            json.dumps(values[c]) if c in ("response", "tool_trace") else values[c]
            for c in columns
        ]
        if record_id is None:
            placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
            sql = f'INSERT INTO "{schema}".{table} ({", ".join(columns)}) VALUES ({placeholders}) RETURNING *'
        else:
            assignments = ", ".join(f"{c} = ${i + 1}" for i, c in enumerate(columns))
            sql = f'UPDATE "{schema}".{table} SET {assignments} WHERE id = ${len(args) + 1} RETURNING *'
            args.append(record_id)
        row = await self._pool.fetchrow(sql, *args)
        return record_dict(row) if row else None

    async def delete_record(self, resource, record_id):
        table, _ = RECORD_COLUMNS[resource]
        schema = self.settings.validated_schema()
        return (
            await self._pool.fetchval(
                f'DELETE FROM "{schema}".{table} WHERE id = $1 RETURNING id', record_id
            )
            is not None
        )

    async def dashboard_data(self, user_id: int, start_date: date, end_date: date):
        schema = self.settings.validated_schema()
        result = {}
        async with (
            self._pool.acquire() as conn,
            conn.transaction(isolation="repeatable_read", readonly=True),
        ):
            for key, table in (
                ("assessment", "recovery_assessments"),
                ("sleep", "sleep_logs"),
                ("checkin", "recovery_checkins"),
            ):
                row = await conn.fetchrow(
                    f'SELECT * FROM "{schema}".{table} WHERE user_id = $1 ORDER BY created_at DESC, id DESC LIMIT 1',
                    user_id,
                )
                result[f"latest_{key}"] = record_dict(row) if row else None
                if key != "checkin":
                    rows = await conn.fetch(
                        f'SELECT * FROM "{schema}".{table} WHERE user_id = $1 AND created_at >= $2 AND created_at < $3 ORDER BY created_at DESC, id DESC',
                        user_id,
                        datetime.combine(start_date, datetime.min.time(), UTC),
                        datetime.combine(
                            end_date + timedelta(days=1), datetime.min.time(), UTC
                        ),
                    )
                    result[f"{key}_trend"] = [record_dict(row) for row in rows]
        return result


RECORD_COLUMNS = {
    "sleep-logs": ("sleep_logs", ("user_id", "duration_minutes", "quality", "notes")),
    "check-ins": (
        "recovery_checkins",
        ("user_id", "energy", "soreness", "stress", "notes"),
    ),
    "assessments": (
        "recovery_assessments",
        ("user_id", "status", "score", "response", "tool_trace"),
    ),
}


def record_dict(row):
    result = dict(row)
    for key in ("response", "tool_trace"):
        if isinstance(result.get(key), str):
            result[key] = json.loads(result[key])
    return result
