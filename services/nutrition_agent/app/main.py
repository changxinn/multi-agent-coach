"""FastAPI entry point for the private, authoritative Nutrition Agent."""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .agent import NutritionAgent
from .calculator import calculate_targets
from .config import settings
from .database import close_db, get_db, init_db
from .schemas import (
    ChatRequest,
    ChatResponse,
    DateRequest,
    EmptyNutritionRequest,
    FoodCatalogueRequest,
    FoodDetailRequest,
    FoodSearchRequest,
    MealPlanConfirmRequest,
    MealPlanCreateRequest,
    MealPlanGenerateRequest,
    MealPlanIdRequest,
    TargetCalculationRequest,
    TargetCalculationResponse,
    TargetsRequest,
    UserRequest,
)
from .service import (
    NutritionFoodDataError,
    NutritionMealPlanSafetyError,
    NutritionMealPlanTransitionError,
    NutritionNotFoundError,
    NutritionProfileIncompleteError,
    NutritionService,
)

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.APP_NAME, version="1.0.0")
agent = NutritionAgent(settings)


async def require_internal_token(
    x_internal_service_token: Annotated[str | None, Header()] = None,
) -> None:
    if (
        not settings.INTERNAL_SERVICE_TOKEN
        or x_internal_service_token != settings.INTERNAL_SERVICE_TOKEN
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid internal service token"
        )


def get_service(db: AsyncSession = Depends(get_db)) -> NutritionService:
    return NutritionService(db)


Service = Annotated[NutritionService, Depends(get_service)]


def translate(error: Exception) -> HTTPException:
    if isinstance(error, NutritionNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(error))
    if isinstance(error, NutritionProfileIncompleteError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))
    if isinstance(error, NutritionMealPlanSafetyError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))
    if isinstance(error, NutritionMealPlanTransitionError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))
    if isinstance(error, NutritionFoodDataError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))
    raise error


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()


@app.on_event("startup")
async def startup() -> None:
    if settings.RUN_MIGRATIONS:
        logger.info("Nutrition migrations enabled; initializing Nutrition database")
        await init_db()
        logger.info("Nutrition database migrations completed")
    else:
        logger.info("Nutrition migrations skipped; RUN_MIGRATIONS is false")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "nutrition-agent"}


@app.post("/v1/nutrition/status", dependencies=[Depends(require_internal_token)])
async def nutrition_status(payload: EmptyNutritionRequest) -> dict[str, str]:
    """Confirm that the private Nutrition Agent endpoint is reachable."""
    del payload
    return {"status": "ready", "service": "nutrition-agent"}


@app.post(
    "/v1/nutrition/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_internal_token)],
)
async def nutrition_chat(payload: ChatRequest) -> ChatResponse:
    """Generate a response from the complete gateway conversation transcript."""
    return ChatResponse(
        message=agent.respond(
            messages=[message.model_dump(exclude_none=True) for message in payload.messages],
            user_profile=payload.user_profile,
        )
    )


@app.post(
    "/v1/nutrition/targets/calculate",
    dependencies=[Depends(require_internal_token)],
    response_model=TargetCalculationResponse,
)
async def calculate_nutrition_targets(
    payload: TargetCalculationRequest,
) -> TargetCalculationResponse:
    """Provide the Phase 1 deterministic calculation to trusted callers only."""
    return calculate_targets(
        sex=payload.sex,
        age=payload.age,
        weight_kg=payload.weight_kg,
        height_cm=payload.height_cm,
        activity_level=payload.activity_level,
        goal=payload.goal,
    )


@app.post(
    "/v1/nutrition/targets/calculate-for-user",
    dependencies=[Depends(require_internal_token)],
)
async def targets_calculate(
    payload: TargetsRequest,
    service: Service,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    try:
        return await service.idempotent(
            payload.user_id,
            "targets.calculate",
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: service.calculate_targets(
                payload.user_id, payload.confirm_apply, payload.profile
            ),
        )
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/targets/active", dependencies=[Depends(require_internal_token)]
)
async def targets_active(payload: UserRequest, service: Service):
    try:
        return await service.get_active_target(payload.user_id)
    except Exception as error:
        raise translate(error) from error


@app.post("/v1/nutrition/foods/search", dependencies=[Depends(require_internal_token)])
async def foods_search(payload: FoodSearchRequest, service: Service):
    try:
        return {"items": await service.search_foods(payload.query)}
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/foods/catalogue", dependencies=[Depends(require_internal_token)]
)
async def foods_catalogue(payload: FoodCatalogueRequest, service: Service):
    return {"items": await service.get_food_catalogue()}


@app.post("/v1/nutrition/foods/detail", dependencies=[Depends(require_internal_token)])
async def foods_detail(payload: FoodDetailRequest, service: Service):
    try:
        return await service.get_food(payload.food_id)
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/meal-plans/create", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_create(
    payload: MealPlanCreateRequest,
    service: Service,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    try:
        return await service.idempotent(
            payload.user_id,
            "meal-plans.create",
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: service.create_meal_plan(payload.user_id, payload),
        )
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/meal-plans/generate", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_generate(
    payload: MealPlanGenerateRequest,
    service: Service,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    try:
        return await service.idempotent(
            payload.user_id,
            "meal-plans.generate",
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: service.generate_meal_plan(payload.user_id, payload),
        )
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/meal-plans/active", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_active(payload: DateRequest, service: Service):
    return {
        "meal_plan": await service.get_active_meal_plan(payload.user_id, payload.date)
    }


@app.post(
    "/v1/nutrition/meal-plans/get", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_get(payload: MealPlanIdRequest, service: Service):
    try:
        return await service.get_meal_plan(payload.user_id, payload.meal_plan_id)
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/meal-plans/list", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_list(payload: UserRequest, service: Service):
    return {"items": await service.list_meal_plans(payload.user_id)}


@app.post(
    "/v1/nutrition/meal-plans/confirm", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_confirm(
    payload: MealPlanConfirmRequest,
    service: Service,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    try:
        return await service.idempotent(
            payload.user_id,
            "meal-plans.confirm",
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: service.confirm_meal_plan(
                payload.user_id, payload.meal_plan_id, profile=payload.profile
            ),
        )
    except Exception as error:
        raise translate(error) from error


@app.post(
    "/v1/nutrition/meal-plans/archive", dependencies=[Depends(require_internal_token)]
)
async def meal_plans_archive(
    payload: MealPlanIdRequest,
    service: Service,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    try:
        return await service.idempotent(
            payload.user_id,
            "meal-plans.archive",
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: service.archive_meal_plan(payload.user_id, payload.meal_plan_id),
        )
    except Exception as error:
        raise translate(error) from error


@app.post("/v1/nutrition/context", dependencies=[Depends(require_internal_token)])
async def nutrition_context(payload: DateRequest, service: Service):
    return await service.get_nutrition_context(payload.user_id, payload.date)
