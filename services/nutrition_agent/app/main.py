"""FastAPI entry point for the standalone Nutrition Agent service."""
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .agent import NutritionAgent
from .assessment import assess_nutrition
from .config import settings
from .repository import NutritionRepository
from .schemas import (
    MealLogCreate,
    MealLogResponse,
    NutritionEvaluateRequest,
    NutritionEvaluateResponse,
    NutritionHistoryResponse,
    NutritionProfileCreate,
    NutritionProfileResponse,
)

repository = NutritionRepository(settings)
agent = NutritionAgent(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage database connection lifecycle."""
    await repository.connect()
    yield
    await repository.close()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Private microservice for nutrition coaching assessments.",
    lifespan=lifespan,
)


async def require_internal_token(
    x_internal_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Validate internal service token."""
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_service_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "nutrition-agent"}


@app.post(
    "/v1/nutrition/profile",
    response_model=NutritionProfileResponse,
    dependencies=[Depends(require_internal_token)],
)
async def create_or_update_profile(payload: NutritionProfileCreate) -> NutritionProfileResponse:
    """Create or update user nutrition profile."""
    profile = await repository.create_or_update_profile(payload)
    return profile


@app.post(
    "/v1/nutrition/meal-logs",
    response_model=MealLogResponse,
    dependencies=[Depends(require_internal_token)],
)
async def create_meal_log(payload: MealLogCreate) -> MealLogResponse:
    """Log a meal."""
    meal_log = await repository.create_meal_log(payload)
    return meal_log


@app.get(
    "/v1/nutrition/history/{user_id}",
    response_model=NutritionHistoryResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_history(user_id: int) -> NutritionHistoryResponse:
    """Get 7-day nutrition history."""
    history = await repository.get_history(user_id)
    return NutritionHistoryResponse(
        user_id=user_id,
        meal_logs_last_7_days=history.meal_logs_last_7_days,
        average_calories=history.average_calories,
        average_protein_g=history.average_protein_g,
        average_carbs_g=history.average_carbs_g,
        average_fat_g=history.average_fat_g,
        adherence_percentage=None,  # TODO: Calculate based on targets
    )


@app.post(
    "/v1/nutrition/evaluate",
    response_model=NutritionEvaluateResponse,
    dependencies=[Depends(require_internal_token)],
)
async def evaluate(payload: NutritionEvaluateRequest) -> NutritionEvaluateResponse:
    """
    Evaluate nutrition status and provide recommendations.

    This is the main endpoint called by the orchestrator.
    """
    # Get nutrition history
    history = await repository.get_history(payload.user_id)

    # Get user profile if exists
    user_profile = await repository.get_profile(payload.user_id)
    profile_dict = dict(user_profile) if user_profile else {}

    # Merge with profile from request
    profile_dict.update(payload.profile)

    # Run deterministic assessment
    assessment = assess_nutrition(payload, history, profile_dict)

    # Apply LLM presentation layer (if enabled)
    assessment = agent.present(assessment, payload.message)

    # Save assessment to database
    await repository.save_assessment(payload.user_id, assessment)

    return assessment
