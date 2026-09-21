"""Authenticated, user-owned nutrition profile, target, and meal endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.routes.auth import get_current_user
from app.api.schemas.nutrition import (
    AdherenceRequest,
    EmptyNutritionRequest,
    FoodCatalogueRequest,
    FoodDetailRequest,
    FoodSearchRequest,
    MealIdRequest,
    MealInput,
    NutritionDateRequest,
    NutritionProfileInput,
    ReplaceMealRequest,
    TargetCalculationRequest,
)
from app.services.nutrition_agent_client import (
    NutritionAgentClient,
    NutritionAgentUnavailableError,
)
from app.services.nutrition_service import (
    NutritionFoodDataError,
    NutritionNotFoundError,
    NutritionProfileIncompleteError,
)

router = APIRouter(prefix="/nutrition")


def get_nutrition_service() -> NutritionAgentClient:
    """Dependency seam for routes and contract tests."""
    return NutritionAgentClient()


NutritionServiceDependency = Annotated[
    NutritionAgentClient, Depends(get_nutrition_service)
]


def not_found(error: NutritionNotFoundError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, str(error))


def food_data_unavailable(error: NutritionFoodDataError) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))


def nutrition_unavailable(error: NutritionAgentUnavailableError) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))


def retired_nutrition_operation() -> None:
    """Return 405 for retired non-POST Nutrition URL shapes."""
    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        "Nutrition endpoints accept POST requests with JSON bodies only",
    )


@router.api_route("/profile", methods=["GET", "PUT"], include_in_schema=False)
@router.api_route("/foods/{food_id}", methods=["GET"], include_in_schema=False)
@router.api_route(
    "/meals/{meal_id}", methods=["PUT", "DELETE"], include_in_schema=False
)
async def reject_retired_nutrition_operation() -> None:
    retired_nutrition_operation()


@router.post("/profile/get")
async def get_profile(
    payload: EmptyNutritionRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    del payload
    try:
        return await service.get_profile(user["id"])
    except NutritionNotFoundError as error:
        raise not_found(error) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/profile/save")
async def update_profile(
    payload: NutritionProfileInput,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
    idempotency_key: str | None = Header(default=None),
):
    try:
        if idempotency_key:
            return await service.update_profile(
                user["id"], payload.model_dump(mode="json"), idempotency_key
            )
        return await service.update_profile(user["id"], payload.model_dump(mode="json"))
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/targets/calculate")
async def calculate_targets_preview_or_apply(
    payload: TargetCalculationRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
    idempotency_key: str | None = Header(default=None),
):
    try:
        if idempotency_key:
            return await service.calculate_targets(
                user["id"], payload.confirm_apply, idempotency_key
            )
        return await service.calculate_targets(user["id"], payload.confirm_apply)
    except NutritionProfileIncompleteError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/targets/active")
async def get_active_targets(
    payload: EmptyNutritionRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    del payload
    try:
        return await service.get_active_target(user["id"])
    except NutritionNotFoundError as error:
        raise not_found(error) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/foods/search")
async def search_foods(
    payload: FoodSearchRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    try:
        return {"items": await service.search_foods(user["id"], payload.query)}
    except NutritionFoodDataError as error:
        raise food_data_unavailable(error) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/foods/catalogue")
async def food_catalogue(
    payload: FoodCatalogueRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    try:
        return {"items": await service.get_food_catalogue(user["id"], payload.limit)}
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/foods/detail")
async def get_food(
    payload: FoodDetailRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    try:
        return await service.get_food(user["id"], payload.food_id)
    except NutritionFoodDataError as error:
        raise food_data_unavailable(error) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/meals", status_code=status.HTTP_201_CREATED)
async def log_meal(
    payload: MealInput,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
    idempotency_key: str | None = Header(default=None),
):
    try:
        if idempotency_key:
            return await service.create_meal(user["id"], payload, idempotency_key)
        return await service.create_meal(user["id"], payload)
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/meals/list")
async def list_meals(
    payload: NutritionDateRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    try:
        return {"items": await service.list_meals(user["id"], payload.date)}
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/meals/replace")
async def replace_meal(
    payload: ReplaceMealRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
    idempotency_key: str | None = Header(default=None),
):
    try:
        if idempotency_key:
            return await service.replace_meal(
                user["id"], payload.meal_id, payload, idempotency_key
            )
        return await service.replace_meal(user["id"], payload.meal_id, payload)
    except NutritionNotFoundError as error:
        raise not_found(error) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/meals/delete")
async def delete_meal(
    payload: MealIdRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
    idempotency_key: str | None = Header(default=None),
):
    try:
        if idempotency_key:
            await service.delete_meal(user["id"], payload.meal_id, idempotency_key)
        else:
            await service.delete_meal(user["id"], payload.meal_id)
    except NutritionNotFoundError as error:
        raise not_found(error) from error
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error
    return {"deleted": True}


@router.post("/daily-summary")
async def daily_summary(
    payload: NutritionDateRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    try:
        return await service.get_daily_summary(user["id"], payload.date)
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error


@router.post("/adherence")
async def adherence(
    payload: AdherenceRequest,
    user: dict = Depends(get_current_user),
    service: NutritionServiceDependency = None,
):
    if (
        payload.to_date < payload.from_date
        or payload.to_date - payload.from_date > timedelta(days=31)
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Date range must be between 0 and 31 days",
        )
    try:
        return {
            "items": await service.get_adherence(
                user["id"], payload.from_date, payload.to_date
            )
        }
    except NutritionAgentUnavailableError as error:
        raise nutrition_unavailable(error) from error
