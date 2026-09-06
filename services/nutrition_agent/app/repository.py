"""Migration-owned PostgreSQL persistence for Nutrition Agent."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import asyncpg

from .assessment import NutritionHistory
from .config import Settings
from .schemas import (
    AssessmentHistoryItem,
    DailyNutritionHistory,
    MealLogCreate,
    MealLogResponse,
    NutritionEvaluateResponse,
    NutritionProfileResponse,
    NutritionProfileUpsert,
)

MIN_COMPARABLE_ADHERENCE_DAYS = 3
MACRO_NUTRIENTS = ("protein_g", "carbs_g", "fat_g")
PROFILE_FIELD_NAMES = (
    "user_id", "timezone", "dietary_preference", "dietary_restrictions", "allergies",
    "meals_per_day", "activity_level", "age", "gender", "weight_kg", "height_cm",
    "created_at", "updated_at",
)
PROFILE_COLUMNS = ", ".join(PROFILE_FIELD_NAMES)


def nutrition_profile_from_row(row: object) -> NutritionProfileResponse:
    """Map a profile record to the API contract across supported JSONB codecs."""
    row_values = dict(row)
    values = {field: row_values[field] for field in PROFILE_FIELD_NAMES if field in row_values}
    for field in ("dietary_restrictions", "allergies"):
        if isinstance(values.get(field), str):
            values[field] = json.loads(values[field])
    return NutritionProfileResponse(**values)


def _adherence_percentage(actual: object, target: object) -> float | None:
    """Return symmetric target adherence only for positive comparable values."""
    try:
        actual_value, target_value = float(actual), float(target)
    except (TypeError, ValueError):
        return None
    if actual_value <= 0 or target_value <= 0:
        return None
    return min(actual_value / target_value, target_value / actual_value) * 100


def nutrition_history_from_daily_rows(rows: list[object]) -> NutritionHistory:
    """Build the assessment-only history projection from daily database totals."""
    daily_rows = [dict(row) for row in rows]
    calorie_adherence = [
        value
        for row in daily_rows
        if (value := _adherence_percentage(row.get("calories"), row.get("target_calories"))) is not None
    ]
    macro_values: dict[str, list[float]] = {nutrient: [] for nutrient in MACRO_NUTRIENTS}
    for row in daily_rows:
        targets = row.get("target_macro_targets")
        if (
            _adherence_percentage(row.get("calories"), row.get("target_calories"))
            is None
            or not isinstance(targets, dict)
        ):
            continue
        for nutrient, values in macro_values.items():
            adherence = _adherence_percentage(row.get(nutrient), targets.get(nutrient))
            if adherence is not None:
                values.append(adherence)
    macro_adherence = {
        nutrient: round(sum(values) / len(values), 1)
        if len(values) >= MIN_COMPARABLE_ADHERENCE_DAYS else None
        for nutrient, values in macro_values.items()
    }
    return NutritionHistory(
        meal_logs_last_7_days=sum(int(row["meal_logs"]) for row in daily_rows),
        average_calories=(
            sum(float(row["calories"]) for row in daily_rows if row.get("calories") is not None)
            / sum(row.get("calories") is not None for row in daily_rows)
            if any(row.get("calories") is not None for row in daily_rows) else None
        ),
        adherence_percentage=(
            round(sum(calorie_adherence) / len(calorie_adherence), 1)
            if len(calorie_adherence) >= MIN_COMPARABLE_ADHERENCE_DAYS else None
        ),
        macro_adherence_percentages=macro_adherence if any(
            value is not None for value in macro_adherence.values()
        ) else None,
    )


class NutritionRepository:
    def __init__(self, settings: Settings):
        self.settings, self.pool = settings, None

    @property
    def _pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Nutrition repository is not connected")
        return self.pool

    def _schema(self) -> str:
        return self.settings.validated_schema()

    async def connect(self) -> None:
        url = self.settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        self.pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
        await self.validate_schema()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def validate_schema(self) -> None:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                f'SELECT version FROM "{self._schema()}".schema_migrations'
            )
        if "010" not in {row["version"] for row in rows}:
            raise RuntimeError("Nutrition database migration 010 is not applied")

    async def upsert_profile(self, user_id: int, payload: NutritionProfileUpsert) -> NutritionProfileResponse:
        p, s = payload.model_dump(), self._schema()
        row = await self._pool.fetchrow(f'''INSERT INTO "{s}".nutrition_profiles
            (user_id,timezone,dietary_preference,dietary_restrictions,allergies,meals_per_day,activity_level,age,gender,weight_kg,height_cm,updated_at)
            VALUES($1,$2,$3,$4::jsonb,$5::jsonb,$6,$7,$8,$9,$10,$11,CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET timezone=EXCLUDED.timezone,dietary_preference=EXCLUDED.dietary_preference,
            dietary_restrictions=EXCLUDED.dietary_restrictions,allergies=EXCLUDED.allergies,meals_per_day=EXCLUDED.meals_per_day,
            activity_level=EXCLUDED.activity_level,age=EXCLUDED.age,gender=EXCLUDED.gender,weight_kg=EXCLUDED.weight_kg,
            height_cm=EXCLUDED.height_cm,updated_at=CURRENT_TIMESTAMP RETURNING {PROFILE_COLUMNS}''', user_id, p["timezone"], p["dietary_preference"],
            json.dumps(p["dietary_restrictions"]), json.dumps(p["allergies"]), p["meals_per_day"], p["activity_level"],
            p["age"], p["gender"], p["weight_kg"], p["height_cm"])
        return nutrition_profile_from_row(row)

    async def get_profile(self, user_id: int) -> NutritionProfileResponse | None:
        row = await self._pool.fetchrow(
            f'SELECT {PROFILE_COLUMNS} FROM "{self._schema()}".nutrition_profiles WHERE user_id=$1', user_id
        )
        return nutrition_profile_from_row(row) if row else None

    async def delete_profile(self, user_id: int) -> bool:
        result = await self._pool.execute(f'DELETE FROM "{self._schema()}".nutrition_profiles WHERE user_id=$1', user_id)
        return result != "DELETE 0"

    async def create_meal(self, user_id: int, payload: MealLogCreate) -> MealLogResponse:
        p, s = payload.model_dump(), self._schema()
        row = await self._pool.fetchrow(f'''INSERT INTO "{s}".meal_logs
            (user_id,meal_type,description,calories,protein_g,carbs_g,fat_g,logged_at)
            VALUES($1,$2,$3,$4,$5,$6,$7,COALESCE($8,CURRENT_TIMESTAMP)) RETURNING *''', user_id, p["meal_type"],
            p["description"], p["calories"], p["protein_g"], p["carbs_g"], p["fat_g"], p["logged_at"])
        return MealLogResponse(**dict(row))

    async def get_meal(self, user_id: int, meal_id: int) -> MealLogResponse | None:
        row = await self._pool.fetchrow(f'SELECT * FROM "{self._schema()}".meal_logs WHERE user_id=$1 AND id=$2', user_id, meal_id)
        return MealLogResponse(**dict(row)) if row else None

    async def replace_meal(self, user_id: int, meal_id: int, payload: MealLogCreate) -> MealLogResponse | None:
        p, s = payload.model_dump(), self._schema()
        row = await self._pool.fetchrow(f'''UPDATE "{s}".meal_logs SET meal_type=$3,description=$4,calories=$5,
            protein_g=$6,carbs_g=$7,fat_g=$8,logged_at=COALESCE($9,logged_at),updated_at=CURRENT_TIMESTAMP
            WHERE user_id=$1 AND id=$2 RETURNING *''', user_id, meal_id, p["meal_type"], p["description"], p["calories"],
            p["protein_g"], p["carbs_g"], p["fat_g"], p["logged_at"])
        return MealLogResponse(**dict(row)) if row else None

    async def delete_meal(self, user_id: int, meal_id: int) -> bool:
        result = await self._pool.execute(f'DELETE FROM "{self._schema()}".meal_logs WHERE user_id=$1 AND id=$2', user_id, meal_id)
        return result != "DELETE 0"

    async def list_meals(
        self,
        user_id: int,
        limit: int,
        offset: int,
        start_date: date | None = None,
        end_date: date | None = None,
        timezone: str | None = None,
    ) -> tuple[list[MealLogResponse], int]:
        s = self._schema()
        if start_date is None:
            rows = await self._pool.fetch(
                f'SELECT * FROM "{s}".meal_logs WHERE user_id=$1 '
                'ORDER BY logged_at DESC,id DESC LIMIT $2 OFFSET $3',
                user_id,
                limit,
                offset,
            )
            total = await self._pool.fetchval(
                f'SELECT count(*) FROM "{s}".meal_logs WHERE user_id=$1', user_id
            )
        else:
            where = (
                'WHERE user_id=$1 '
                'AND logged_at >= ($2::date::timestamp AT TIME ZONE $4) '
                'AND logged_at < (($3::date + 1)::timestamp AT TIME ZONE $4)'
            )
            rows = await self._pool.fetch(
                f'SELECT * FROM "{s}".meal_logs {where} '
                'ORDER BY logged_at DESC,id DESC LIMIT $5 OFFSET $6',
                user_id,
                start_date,
                end_date,
                timezone,
                limit,
                offset,
            )
            total = await self._pool.fetchval(
                f'SELECT count(*) FROM "{s}".meal_logs {where}',
                user_id,
                start_date,
                end_date,
                timezone,
            )
        return [MealLogResponse(**dict(row)) for row in rows], int(total)

    async def history(self, user_id: int) -> NutritionHistory:
        """Return seven UTC-local-day totals and applicable target-version adherence."""
        s = self._schema()
        rows = await self._pool.fetch(
            f'''WITH daily_logs AS (
                    SELECT (logged_at AT TIME ZONE 'UTC')::date AS day,
                           count(*)::int AS meal_logs,
                           sum(calories)::float AS calories,
                           sum(protein_g)::float AS protein_g,
                           sum(carbs_g)::float AS carbs_g,
                           sum(fat_g)::float AS fat_g
                    FROM "{s}".meal_logs
                    WHERE user_id = $1
                      AND logged_at >= (
                          date_trunc('day', CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - interval '6 days'
                      ) AT TIME ZONE 'UTC'
                      AND logged_at < (
                          date_trunc('day', CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + interval '1 day'
                      ) AT TIME ZONE 'UTC'
                    GROUP BY (logged_at AT TIME ZONE 'UTC')::date
                )
                SELECT daily_logs.*, target.recommended_calories::float AS target_calories,
                       target.macro_targets AS target_macro_targets
                FROM daily_logs
                LEFT JOIN LATERAL (
                    SELECT recommended_calories, macro_targets
                    FROM "{s}".nutrition_targets
                    WHERE user_id = $1 AND effective_from <= daily_logs.day
                      AND (effective_to IS NULL OR effective_to >= daily_logs.day)
                    ORDER BY effective_from DESC, version DESC LIMIT 1
                ) target ON true
                ORDER BY daily_logs.day''',
            user_id,
        )
        return nutrition_history_from_daily_rows(rows)

    async def daily_history(
        self, user_id: int, start_date: date, end_date: date, timezone: str
    ) -> DailyNutritionHistory:
        """Aggregate logs and effective target versions by the caller's local date."""
        s = self._schema()
        rows = await self._pool.fetch(
            f'''WITH calendar AS (
                    SELECT generate_series($2::date, $3::date, interval '1 day')::date AS day
                ), daily_logs AS (
                    SELECT (logged_at AT TIME ZONE $4)::date AS day,
                           count(*)::int AS meal_logs,
                           sum(calories)::float AS calories,
                           sum(protein_g)::float AS protein_g,
                           sum(carbs_g)::float AS carbs_g,
                           sum(fat_g)::float AS fat_g
                    FROM "{s}".meal_logs
                    WHERE user_id = $1
                      AND logged_at >= ($2::date::timestamp AT TIME ZONE $4)
                      AND logged_at < (($3::date + 1)::timestamp AT TIME ZONE $4)
                    GROUP BY (logged_at AT TIME ZONE $4)::date
                )
                SELECT calendar.day, COALESCE(daily_logs.meal_logs, 0) AS meal_logs,
                       daily_logs.calories, daily_logs.protein_g, daily_logs.carbs_g, daily_logs.fat_g,
                       target.recommended_calories::float AS target_calories
                FROM calendar
                LEFT JOIN daily_logs ON daily_logs.day = calendar.day
                LEFT JOIN LATERAL (
                    SELECT recommended_calories
                    FROM "{s}".nutrition_targets
                    WHERE user_id = $1 AND effective_from <= calendar.day
                      AND (effective_to IS NULL OR effective_to >= calendar.day)
                    ORDER BY effective_from DESC, version DESC LIMIT 1
                ) target ON true
                ORDER BY calendar.day''',
            user_id, start_date, end_date, timezone,
        )
        days: list[dict] = []
        adherence_values: list[float] = []
        nutrient_values: dict[str, list[float]] = {key: [] for key in ("calories", "protein_g", "carbs_g", "fat_g")}
        for row in rows:
            item = dict(row)
            calories, target_calories = item["calories"], item["target_calories"]
            adherence = None
            adherence = _adherence_percentage(calories, target_calories)
            if adherence is not None:
                adherence_values.append(adherence)
            for nutrient, values in nutrient_values.items():
                if item[nutrient] is not None:
                    values.append(float(item[nutrient]))
            days.append({**item, "calorie_adherence_percentage": adherence})
        averages = {
            f"average_daily_{nutrient}": (sum(values) / len(values) if values else None)
            for nutrient, values in nutrient_values.items()
        }
        return DailyNutritionHistory(
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
            days_with_logs=sum(day["meal_logs"] > 0 for day in days),
            days=days,
            **averages,
            calorie_adherence_percentage=(
                round(sum(adherence_values) / len(adherence_values), 1)
                if len(adherence_values) >= 3 else None
            ),
        )

    async def save_target(self, user_id: int, inputs: dict, calculation: dict, effective_from: date) -> dict:
        s = self._schema()
        async with self._pool.acquire() as connection, connection.transaction():
            # A row lock cannot serialize a first target for a user, so use a
            # transaction-scoped per-user advisory lock for every write.
            await connection.execute("SELECT pg_advisory_xact_lock($1)", user_id)
            await connection.execute(f'''UPDATE "{s}".nutrition_targets AS target
                SET effective_to=$2-1
                WHERE target.user_id=$1 AND target.effective_from < $2
                  AND (target.effective_to IS NULL OR target.effective_to >= $2)
                  AND NOT EXISTS (
                      SELECT 1 FROM "{s}".nutrition_targets AS revision
                      WHERE revision.user_id=target.user_id
                        AND revision.effective_from=target.effective_from
                        AND revision.version>target.version
                  )''', user_id, effective_from)
            row = await connection.fetchrow(f'''INSERT INTO "{s}".nutrition_targets
                (user_id,inputs,recommended_calories,macro_targets,policy_version,effective_from,effective_to,version)
                VALUES($1,$2::jsonb,$3,$4::jsonb,$5,$6,(
                    SELECT min(effective_from)-1 FROM "{s}".nutrition_targets
                    WHERE user_id=$1 AND effective_from>$6
                ),COALESCE((
                    SELECT max(version)+1 FROM "{s}".nutrition_targets
                    WHERE user_id=$1 AND effective_from=$6
                ),1)) RETURNING *''', user_id, json.dumps(inputs),
                calculation["recommended_calories"], json.dumps(calculation["macro_targets"]), calculation["policy_version"], effective_from)
        return dict(row)

    async def current_target(self, user_id: int, on_date: date) -> dict | None:
        row = await self._pool.fetchrow(f'''SELECT * FROM "{self._schema()}".nutrition_targets
            WHERE user_id=$1 AND effective_from <= $2 AND (effective_to IS NULL OR effective_to >= $2)
            ORDER BY effective_from DESC, version DESC LIMIT 1''', user_id, on_date)
        return dict(row) if row else None

    async def save_assessment(self, user_id: int, assessment: NutritionEvaluateResponse) -> None:
        s = self._schema()
        safety = {"findings": [x.model_dump() for x in assessment.safety_findings], "escalation": assessment.escalation.model_dump() if assessment.escalation else None}
        await self._pool.execute(f'''INSERT INTO "{s}".nutrition_assessments
            (user_id,status,score,tdee,macro_targets,response,tool_trace,policy_version,trigger_codes,safety_projection,target_summary,presentation_message,recommendations)
            VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,'[]'::jsonb,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,$12::jsonb)''', user_id,
            assessment.status, assessment.score, assessment.tdee, json.dumps(assessment.macro_targets), json.dumps({"message": assessment.message}),
            assessment.policy_version, json.dumps([x.code for x in assessment.safety_findings]), json.dumps(safety),
            json.dumps({"tdee": assessment.tdee, "macro_targets": assessment.macro_targets}), assessment.message,
            json.dumps(assessment.recommendations))

    async def list_assessments(
        self, user_id: int, limit: int, offset: int
    ) -> tuple[list[AssessmentHistoryItem], int]:
        """Return the privacy-safe assessment projection, never raw request data."""
        s = self._schema()
        rows = await self._pool.fetch(
            f'''SELECT id, status, score, tdee, macro_targets, presentation_message, safety_projection,
                       recommendations, COALESCE(policy_version, 'nutrition-safety-v1') AS policy_version,
                       created_at
                FROM "{s}".nutrition_assessments
                WHERE user_id = $1
                ORDER BY created_at DESC NULLS LAST, id DESC
                LIMIT $2 OFFSET $3''',
            user_id, limit, offset,
        )
        total = await self._pool.fetchval(
            f'SELECT count(*) FROM "{s}".nutrition_assessments WHERE user_id=$1', user_id
        )
        items: list[AssessmentHistoryItem] = []
        for row in rows:
            value = dict(row)
            safety = value.pop("safety_projection") or {}
            message = value.pop("presentation_message")
            items.append(AssessmentHistoryItem(
                **value,
                message=message,
                safety_findings=safety.get("findings", []),
                escalation=safety.get("escalation"),
            ))
        return items, int(total)

    async def search_food_cache(self, query: str, limit: int = 10) -> list[dict]:
        rows = await self._pool.fetch(f'''SELECT * FROM "{self._schema()}".food_cache WHERE name ILIKE $1
            ORDER BY lower(name),fdc_id LIMIT $2''', f"%{query}%", limit)
        return [dict(row) for row in rows]

    async def get_cached_food(self, fdc_id: int) -> dict | None:
        row = await self._pool.fetchrow(f'SELECT * FROM "{self._schema()}".food_cache WHERE fdc_id=$1', fdc_id)
        return dict(row) if row else None

    async def upsert_cached_food(self, food: dict) -> dict:
        """Store a normalized USDA food with the configured freshness window."""
        s = self._schema()
        now = datetime.now(UTC)
        row = await self._pool.fetchrow(
            f'''INSERT INTO "{s}".food_cache
                (fdc_id,name,brand,serving_size_g,calories,protein_g,carbs_g,fat_g,fiber_g,category,
                 last_updated,fetched_at,refresh_after,source,suppression_until)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11,$12,'usda',NULL)
                ON CONFLICT(fdc_id) DO UPDATE SET
                    name=EXCLUDED.name, brand=EXCLUDED.brand, serving_size_g=EXCLUDED.serving_size_g,
                    calories=EXCLUDED.calories, protein_g=EXCLUDED.protein_g, carbs_g=EXCLUDED.carbs_g,
                    fat_g=EXCLUDED.fat_g, fiber_g=EXCLUDED.fiber_g, category=EXCLUDED.category,
                    last_updated=EXCLUDED.last_updated, fetched_at=EXCLUDED.fetched_at,
                    refresh_after=EXCLUDED.refresh_after, source=EXCLUDED.source,
                    suppression_until=NULL
                RETURNING *''',
            food["fdc_id"], food["name"], food.get("brand"), food.get("serving_size_g"),
            food.get("calories"), food.get("protein_g"), food.get("carbs_g"), food.get("fat_g"),
            food.get("fiber_g"), food.get("category"), now,
            now + timedelta(days=self.settings.FOOD_CACHE_FRESH_DAYS),
        )
        return dict(row)

    async def suppress_food_refresh(self, fdc_id: int, until: datetime) -> None:
        """Bound repeated refresh attempts for an already-cached food after USDA failure."""
        await self._pool.execute(
            f'UPDATE "{self._schema()}".food_cache SET suppression_until=$2 WHERE fdc_id=$1',
            fdc_id,
            until,
        )

    async def get_food_search_suppression(self, normalized_query: str) -> dict | None:
        row = await self._pool.fetchrow(
            f'''SELECT normalized_query, suppression_until, reason
                FROM "{self._schema()}".food_search_suppressions
                WHERE normalized_query=$1''',
            normalized_query,
        )
        return dict(row) if row else None

    async def suppress_food_search(
        self, normalized_query: str, until: datetime, reason: str
    ) -> None:
        """Persist bounded search retry suppression without storing raw input."""
        await self._pool.execute(
            f'''INSERT INTO "{self._schema()}".food_search_suppressions
                (normalized_query, suppression_until, reason)
                VALUES($1,$2,$3)
                ON CONFLICT(normalized_query) DO UPDATE SET
                    suppression_until=EXCLUDED.suppression_until,
                    reason=EXCLUDED.reason,
                    updated_at=CURRENT_TIMESTAMP''',
            normalized_query,
            until,
            reason,
        )