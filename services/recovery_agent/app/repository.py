"""PostgreSQL repository owned by the Recovery Agent service."""
from __future__ import annotations

import json
from datetime import datetime

import asyncpg

from .assessment import RecoveryHistory
from .config import Settings
from .schemas import RecoveryCheckInCreate, RecoveryEvaluateResponse, SleepLogCreate


class RecoveryRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        database_url = self.settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
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
                    user_id BIGINT NOT NULL REFERENCES "{schema}".users(id) ON DELETE CASCADE,
                    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 0 AND 1440),
                    quality INTEGER NOT NULL CHECK (quality BETWEEN 1 AND 5),
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )'''
            )
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".recovery_checkins (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES "{schema}".users(id) ON DELETE CASCADE,
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
                    user_id BIGINT NOT NULL REFERENCES "{schema}".users(id) ON DELETE CASCADE,
                    status VARCHAR(16) NOT NULL,
                    score INTEGER NOT NULL,
                    response JSONB NOT NULL,
                    tool_trace JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )'''
            )
            await conn.execute(f'CREATE INDEX IF NOT EXISTS idx_sleep_logs_user_created ON "{schema}".sleep_logs(user_id, created_at DESC)')
            await conn.execute(f'CREATE INDEX IF NOT EXISTS idx_recovery_checkins_user_created ON "{schema}".recovery_checkins(user_id, created_at DESC)')

    async def create_sleep_log(self, payload: SleepLogCreate) -> asyncpg.Record:
        schema = self.settings.validated_schema()
        return await self._pool.fetchrow(
            f'''INSERT INTO "{schema}".sleep_logs (user_id, duration_minutes, quality, notes)
                VALUES ($1, $2, $3, $4)
                RETURNING id, user_id, duration_minutes, quality, notes, created_at''',
            payload.user_id, payload.duration_minutes, payload.quality, payload.notes,
        )

    async def create_checkin(self, payload: RecoveryCheckInCreate) -> None:
        schema = self.settings.validated_schema()
        await self._pool.execute(
            f'''INSERT INTO "{schema}".recovery_checkins (user_id, energy, soreness, stress, notes)
                VALUES ($1, $2, $3, $4, $5)''',
            payload.user_id, payload.energy, payload.soreness, payload.stress, payload.notes,
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
            average_sleep_minutes=float(row["avg_sleep_minutes"]) if row["avg_sleep_minutes"] is not None else None,
            average_sleep_quality=float(row["avg_sleep_quality"]) if row["avg_sleep_quality"] is not None else None,
            check_ins_last_7_days=int(row["checkins"]),
            workouts_last_7_days=0,
        )

    async def save_assessment(self, user_id: int, assessment: RecoveryEvaluateResponse) -> None:
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
