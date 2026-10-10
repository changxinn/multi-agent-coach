"""Read-only aggregation for the authenticated Daily Agent Command Center."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.dashboard import (
    DailyCommandCenterResponse,
    DashboardAction,
    DashboardDomainError,
    NutritionDashboardSnapshot,
    NutritionTrendPoint,
    RecoveryDashboardSnapshot,
    RecoveryTrendPoint,
    TrainingDashboardSnapshot,
)
from app.services.nutrition_service import NutritionService
from app.services.recovery_agent_client import recovery_agent_client

TRAINING_MESSAGE = "Your workout log is not yet connected to the daily dashboard."
NUTRITION_UNAVAILABLE_MESSAGE = "Nutrition status is temporarily unavailable."
RECOVERY_UNAVAILABLE_MESSAGE = "Recovery status is temporarily unavailable."


def _number(value: Any) -> float | None:
    return float(value) if value is not None else None


class DailyCommandCenterService:
    def __init__(self, db: AsyncSession, nutrition_service: NutritionService):
        self.db = db
        self.nutrition_service = nutrition_service

    async def get(
        self, user_id: int, dashboard_date: date | None = None
    ) -> DailyCommandCenterResponse:
        dashboard_date = dashboard_date or datetime.now(UTC).date()
        start_date = dashboard_date - timedelta(days=6)
        errors: list[DashboardDomainError] = []

        nutrition = await self._nutrition_snapshot(
            user_id, dashboard_date, start_date, errors
        )
        recovery = await self._recovery_snapshot(
            user_id, dashboard_date, start_date, errors
        )
        training = TrainingDashboardSnapshot(message=TRAINING_MESSAGE)

        return DailyCommandCenterResponse(
            generated_at=datetime.now(UTC),
            dashboard_date=dashboard_date,
            training=training,
            nutrition=nutrition,
            recovery=recovery,
            actions=self._actions(nutrition, recovery),
            errors=errors,
        )

    async def _nutrition_snapshot(
        self,
        user_id: int,
        dashboard_date: date,
        start_date: date,
        errors: list[DashboardDomainError],
    ) -> NutritionDashboardSnapshot:
        try:
            summary, adherence = await self._nutrition_data(
                user_id, dashboard_date, start_date
            )
        except Exception:
            errors.append(
                DashboardDomainError(
                    domain="nutrition", message=NUTRITION_UNAVAILABLE_MESSAGE
                )
            )
            return NutritionDashboardSnapshot(
                status="unavailable", message=NUTRITION_UNAVAILABLE_MESSAGE
            )

        target = summary.get("target")
        trend_by_date = {item["summary_date"]: item for item in adherence}
        trend = [
            NutritionTrendPoint(
                date=current,
                calorie_adherence_pct=_number(
                    trend_by_date.get(current, {}).get("calorie_adherence_pct")
                ),
                protein_adherence_pct=_number(
                    trend_by_date.get(current, {}).get("protein_adherence_pct")
                ),
                meal_count=int(trend_by_date.get(current, {}).get("meal_count", 0)),
            )
            for current in self._date_range(start_date, dashboard_date)
        ]
        if target is None:
            return NutritionDashboardSnapshot(
                status="no_target",
                message="Set nutrition targets to see today's progress.",
                calories=_number(summary.get("calories")),
                protein_g=_number(summary.get("protein_g")),
                meal_count=int(summary.get("meal_count", 0)),
                trend=trend,
            )
        remaining = summary.get("remaining", {})
        return NutritionDashboardSnapshot(
            status="available",
            calories=_number(summary.get("calories")),
            protein_g=_number(summary.get("protein_g")),
            meal_count=int(summary.get("meal_count", 0)),
            calorie_target_kcal=_number(target.get("calorie_target_kcal")),
            protein_target_g=_number(target.get("protein_target_g")),
            remaining_calories=_number(remaining.get("calories")),
            remaining_protein_g=_number(remaining.get("protein_g")),
            calorie_adherence_pct=_number(summary.get("calorie_adherence_pct")),
            protein_adherence_pct=_number(summary.get("protein_adherence_pct")),
            trend=trend,
        )

    async def _nutrition_data(
        self, user_id: int, dashboard_date: date, start_date: date
    ):
        summary = await self.nutrition_service.get_daily_summary(
            user_id, dashboard_date
        )
        adherence = await self.nutrition_service.get_adherence(
            user_id, start_date, dashboard_date
        )
        return summary, adherence

    async def _recovery_snapshot(
        self,
        user_id: int,
        dashboard_date: date,
        start_date: date,
        errors: list[DashboardDomainError],
    ) -> RecoveryDashboardSnapshot:
        try:
            (
                latest_assessment,
                latest_sleep,
                latest_checkin,
                trend,
            ) = await self._recovery_data(user_id, dashboard_date, start_date)
        except Exception:
            errors.append(
                DashboardDomainError(
                    domain="recovery", message=RECOVERY_UNAVAILABLE_MESSAGE
                )
            )
            return RecoveryDashboardSnapshot(
                status="unavailable", message=RECOVERY_UNAVAILABLE_MESSAGE
            )

        if latest_assessment is None:
            return RecoveryDashboardSnapshot(
                status="no_assessment",
                message="No recovery assessment yet. Log sleep or complete a recovery check-in.",
                sleep_duration_minutes=self._value(latest_sleep, "duration_minutes"),
                sleep_quality=self._value(latest_sleep, "quality"),
                sleep_logged_at=self._value(latest_sleep, "created_at"),
                energy=self._value(latest_checkin, "energy"),
                soreness=self._value(latest_checkin, "soreness"),
                stress=self._value(latest_checkin, "stress"),
                check_in_created_at=self._value(latest_checkin, "created_at"),
                trend=trend,
            )
        return RecoveryDashboardSnapshot(
            status=latest_assessment["status"],
            assessment_score=latest_assessment["score"],
            assessment_created_at=latest_assessment["created_at"],
            sleep_duration_minutes=self._value(latest_sleep, "duration_minutes"),
            sleep_quality=self._value(latest_sleep, "quality"),
            sleep_logged_at=self._value(latest_sleep, "created_at"),
            energy=self._value(latest_checkin, "energy"),
            soreness=self._value(latest_checkin, "soreness"),
            stress=self._value(latest_checkin, "stress"),
            check_in_created_at=self._value(latest_checkin, "created_at"),
            trend=trend,
        )

    async def _recovery_data(
        self, user_id: int, dashboard_date: date, start_date: date
    ):
        data = await recovery_agent_client.dashboard_data(
            user_id, start_date, dashboard_date
        )
        latest_assessment = data["latest_assessment"]
        latest_sleep = data["latest_sleep"]
        latest_checkin = data["latest_checkin"]
        rows = (data["sleep_trend"], data["assessment_trend"])
        sleep_by_day = self._latest_by_day(rows[0])
        assessments_by_day = self._latest_by_day(rows[1])
        trend = [
            RecoveryTrendPoint(
                date=current,
                sleep_duration_minutes=self._value(
                    sleep_by_day.get(current), "duration_minutes"
                ),
                sleep_quality=self._value(sleep_by_day.get(current), "quality"),
                assessment_status=self._value(
                    assessments_by_day.get(current), "status"
                ),
                assessment_score=self._value(assessments_by_day.get(current), "score"),
            )
            for current in self._date_range(start_date, dashboard_date)
        ]
        return latest_assessment, latest_sleep, latest_checkin, trend

    @staticmethod
    def _latest_by_day(rows: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
        by_day: dict[date, dict[str, Any]] = {}
        for row in rows:
            created_at = row["created_at"]
            day = (
                created_at.astimezone(UTC).date()
                if created_at.tzinfo
                else created_at.date()
            )
            by_day.setdefault(day, row)
        return by_day

    @staticmethod
    def _value(row: dict[str, Any] | None, key: str):
        return row.get(key) if row else None

    @staticmethod
    def _date_range(start_date: date, end_date: date):
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)

    @staticmethod
    def _actions(
        nutrition: NutritionDashboardSnapshot, recovery: RecoveryDashboardSnapshot
    ) -> list[DashboardAction]:
        actions: list[DashboardAction] = []

        def add(
            action_id: str, severity: str, title: str, description: str, route: str
        ):
            if len(actions) < 3:
                actions.append(
                    DashboardAction(
                        id=action_id,
                        priority=len(actions) + 1,
                        severity=severity,
                        title=title,
                        description=description,
                        route=route,
                    )
                )

        if recovery.status == "escalate":
            add(
                "recovery-escalation",
                "critical",
                "Seek appropriate professional care",
                "Your latest recovery assessment recommends appropriate professional care. Review your recovery details.",
                "/recovery-table",
            )
        elif recovery.status == "red":
            add(
                "recovery-attention",
                "warning",
                "Recovery needs attention",
                "Your latest recovery assessment needs attention. Review your recovery details before deciding on today's session.",
                "/recovery-table",
            )
        elif recovery.status == "amber":
            add(
                "recovery-caution",
                "warning",
                "Recovery needs attention",
                "Your latest recovery assessment is amber. Review your recovery details before deciding on today's session.",
                "/recovery-table",
            )
        elif recovery.status == "no_assessment":
            add(
                "recovery-check-in",
                "info",
                "Check in on recovery",
                "Log sleep or complete a recovery check-in to see your latest recovery status.",
                "/recovery-table",
            )

        if nutrition.status == "no_target":
            add(
                "nutrition-targets",
                "info",
                "Set nutrition targets",
                "Set nutrition targets to see how today's meals support your goal.",
                "/nutrition",
            )
        elif nutrition.status == "available" and nutrition.meal_count == 0:
            add(
                "nutrition-log-meal",
                "info",
                "Log your first meal",
                "Log a meal to keep today's nutrition progress up to date.",
                "/nutrition",
            )
        elif (
            nutrition.status == "available" and (nutrition.remaining_protein_g or 0) > 0
        ):
            add(
                "nutrition-protein",
                "info",
                "Plan your next protein serving",
                f"You have {nutrition.remaining_protein_g:g} g of protein remaining toward today's target.",
                "/nutrition",
            )

        add(
            "training-coach",
            "info",
            "Ask your Training Coach",
            "Ask the Training Planner for today's session, form guidance, or a program adjustment.",
            "/chat",
        )
        return actions
