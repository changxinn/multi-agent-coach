"""Authenticated personal dashboard endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.api.schemas.dashboard import (
    DailyCommandCenterResponse,
    TrainingWorkoutResponse,
)
from app.db.database import get_db
from app.services.daily_command_center_service import DailyCommandCenterService
from app.services.daily_training_workout_service import DailyTrainingWorkoutService
from app.services.nutrition_service import NutritionService

router = APIRouter(prefix="/dashboard")


def get_daily_command_center_service(
    db: AsyncSession = Depends(get_db),
) -> DailyCommandCenterService:
    return DailyCommandCenterService(db, NutritionService(db))


DailyCommandCenterServiceDependency = Annotated[
    DailyCommandCenterService, Depends(get_daily_command_center_service)
]


def get_daily_training_workout_service(
    db: AsyncSession = Depends(get_db),
) -> DailyTrainingWorkoutService:
    return DailyTrainingWorkoutService(db)


DailyTrainingWorkoutServiceDependency = Annotated[
    DailyTrainingWorkoutService, Depends(get_daily_training_workout_service)
]


@router.get("/daily-command-center", response_model=DailyCommandCenterResponse)
async def get_daily_command_center(
    current_user: dict = Depends(get_current_user),
    service: DailyCommandCenterServiceDependency = None,
):
    return await service.get(current_user["id"])


@router.post("/training/today", response_model=TrainingWorkoutResponse)
async def get_daily_training_workout(
    refresh: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
    service: DailyTrainingWorkoutServiceDependency = None,
):
    """Return the authenticated athlete's persisted or newly generated daily workout."""
    return await service.get(current_user["id"], refresh=refresh)
