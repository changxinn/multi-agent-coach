"""Authenticated browser gateway for Main API-owned training state."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.api.schemas.training import (
    EmptyTrainingRequest,
    ExerciseSearchInput,
    ProgramAdaptInput,
    ProgressInput,
    TrainingPreferencesInput,
    WorkoutListInput,
    WorkoutLogInput,
)
from app.db.database import get_db
from app.services.daily_training_workout_service import DailyTrainingWorkoutService
from app.services.training_agent_client import (
    TrainingAgentClient,
    TrainingAgentUnavailableError,
)
from app.services.training_progress_service import TrainingProgressService
from app.services.user_profile_service import UserProfileService

router = APIRouter(prefix="/training")


def get_training_service(db: AsyncSession = Depends(get_db)) -> TrainingProgressService:
    return TrainingProgressService(db)


def get_training_agent() -> TrainingAgentClient:
    return TrainingAgentClient()


TrainingService = Annotated[TrainingProgressService, Depends(get_training_service)]
TrainingAgent = Annotated[TrainingAgentClient, Depends(get_training_agent)]


def unavailable(error: TrainingAgentUnavailableError) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))


async def agent_context(user_id: int, service: TrainingProgressService, db: AsyncSession) -> dict[str, Any]:
    profile = await UserProfileService(db).get_user_profile(user_id)
    preferences = await service.preferences(user_id)
    progress = await service.progress(user_id, 28)
    recovery = await DailyTrainingWorkoutService(db)._recovery_snapshot(user_id, datetime.now(UTC).date())
    return {"profile": {**profile, "training_preferences": preferences}, "recovery_status": recovery.status, "workout_history_summary": progress}


@router.post("/preferences/get")
async def get_preferences(payload: EmptyTrainingRequest, user: dict = Depends(get_current_user), service: TrainingService = None):
    del payload
    return await service.preferences(user["id"])


@router.post("/preferences/update")
async def update_preferences(payload: TrainingPreferencesInput, user: dict = Depends(get_current_user), service: TrainingService = None):
    return await service.save_preferences(user["id"], payload.model_dump())


@router.post("/exercises/search")
async def search_exercises(payload: ExerciseSearchInput, user: dict = Depends(get_current_user), agent: TrainingAgent = None):
    try:
        return await agent.exercises_search(user["id"], payload.query)
    except TrainingAgentUnavailableError as error:
        raise unavailable(error) from error


@router.post("/exercises/lookup")
async def lookup_exercise(payload: ExerciseSearchInput, user: dict = Depends(get_current_user), agent: TrainingAgent = None):
    try:
        return await agent.exercise_lookup(user["id"], payload.query)
    except TrainingAgentUnavailableError as error:
        raise unavailable(error) from error


@router.post("/programs/generate")
async def generate_program(payload: EmptyTrainingRequest, user: dict = Depends(get_current_user), service: TrainingService = None, agent: TrainingAgent = None, db: AsyncSession = Depends(get_db)):
    del payload
    try:
        return await agent.generate_program(user["id"], **await agent_context(user["id"], service, db))
    except TrainingAgentUnavailableError as error:
        raise unavailable(error) from error


@router.post("/programs/list")
async def list_programs(payload: EmptyTrainingRequest, user: dict = Depends(get_current_user), agent: TrainingAgent = None):
    del payload
    try:
        return await agent.list_programs(user["id"])
    except TrainingAgentUnavailableError as error:
        raise unavailable(error) from error


@router.post("/programs/adapt")
async def adapt_program(payload: ProgramAdaptInput, user: dict = Depends(get_current_user), service: TrainingService = None, agent: TrainingAgent = None, db: AsyncSession = Depends(get_db)):
    try:
        return await agent.adapt_program(user["id"], payload.reason, **await agent_context(user["id"], service, db))
    except TrainingAgentUnavailableError as error:
        raise unavailable(error) from error


@router.post("/workouts/log")
async def log_workout(payload: WorkoutLogInput, user: dict = Depends(get_current_user), service: TrainingService = None, idempotency_key: str | None = Header(default=None)):
    return await service.log_workout(user["id"], payload.model_dump(), idempotency_key)


@router.post("/workouts/list")
async def list_workouts(payload: WorkoutListInput, user: dict = Depends(get_current_user), service: TrainingService = None):
    return {"items": await service.list_workouts(user["id"], payload.days, payload.limit)}


@router.post("/progress")
async def progress(payload: ProgressInput, user: dict = Depends(get_current_user), service: TrainingService = None):
    return await service.progress(user["id"], payload.days)