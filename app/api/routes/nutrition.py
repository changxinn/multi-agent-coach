"""Authenticated public Nutrition API boundary."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.routes.auth import get_current_user
from app.api.schemas.nutrition import (
    FoodResponse,
    FoodSearchResponse,
    MealLogWriteRequest,
    MealPlanPublicRequest,
    NutritionProfileWriteRequest,
    TargetCalculatePublicRequest,
    TargetSavePublicRequest,
)
from app.services.nutrition_agent_client import (
    NutritionAgentError,
    nutrition_agent_client,
)

router = APIRouter()


def mapped_nutrition_error(error: NutritionAgentError) -> HTTPException:
    """Translate sanitized private errors without exposing private details."""
    if error.status_code == 404:
        return HTTPException(404, {"code": error.code})
    if error.status_code == 422:
        return HTTPException(422, {"code": error.code, "message": error.message})
    return HTTPException(503, {"code": "DEPENDENCY_UNAVAILABLE"})


async def nutrition_operation(operation: Any):
    """Map a named Nutrition Agent client operation to the public boundary."""
    try:
        return await operation
    except NutritionAgentError as error:
        raise mapped_nutrition_error(error) from error


@router.get("/nutrition/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    return await nutrition_operation(nutrition_agent_client.get_profile(int(current_user["id"])))


@router.put("/nutrition/profile")
async def put_profile(
    payload: NutritionProfileWriteRequest, current_user: dict = Depends(get_current_user)
):
    return await nutrition_operation(
        nutrition_agent_client.upsert_profile(int(current_user["id"]), payload.model_dump(mode="json"))
    )


@router.delete("/nutrition/profile", status_code=204)
async def delete_profile(current_user: dict = Depends(get_current_user)):
    await nutrition_operation(nutrition_agent_client.delete_profile(int(current_user["id"])))
    return Response(status_code=204)


@router.post("/nutrition/meal-logs", status_code=201)
async def create_meal(
    payload: MealLogWriteRequest, current_user: dict = Depends(get_current_user)
):
    return await nutrition_operation(
        nutrition_agent_client.create_meal_log(int(current_user["id"]), payload.model_dump(mode="json"))
    )


@router.get("/nutrition/meal-logs")
async def list_meals(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    start_date: date | None = None,
    end_date: date | None = None,
    timezone: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if start_date is not None:
        params["start_date"] = start_date.isoformat()
    if end_date is not None:
        params["end_date"] = end_date.isoformat()
    if timezone is not None:
        params["timezone"] = timezone
    return await nutrition_operation(
        nutrition_agent_client.list_meal_logs(int(current_user["id"]), params)
    )


@router.get("/nutrition/meal-logs/{meal_id}")
async def get_meal(meal_id: int, current_user: dict = Depends(get_current_user)):
    return await nutrition_operation(
        nutrition_agent_client.get_meal_log(int(current_user["id"]), meal_id)
    )


@router.put("/nutrition/meal-logs/{meal_id}")
async def put_meal(
    meal_id: int,
    payload: MealLogWriteRequest,
    current_user: dict = Depends(get_current_user),
):
    return await nutrition_operation(
        nutrition_agent_client.replace_meal_log(
            int(current_user["id"]), meal_id, payload.model_dump(mode="json")
        )
    )


@router.delete("/nutrition/meal-logs/{meal_id}", status_code=204)
async def delete_meal(meal_id: int, current_user: dict = Depends(get_current_user)):
    await nutrition_operation(nutrition_agent_client.delete_meal_log(int(current_user["id"]), meal_id))
    return Response(status_code=204)


@router.post("/nutrition/targets/calculate")
async def calculate_target(
    payload: TargetCalculatePublicRequest, current_user: dict = Depends(get_current_user)
):
    return await nutrition_operation(
        nutrition_agent_client.calculate_targets(
            int(current_user["id"]), payload.model_dump(mode="json")
        )
    )


@router.post("/nutrition/targets", status_code=201)
async def save_target(
    payload: TargetSavePublicRequest, current_user: dict = Depends(get_current_user)
):
    return await nutrition_operation(
        nutrition_agent_client.save_target(int(current_user["id"]), payload.model_dump(mode="json"))
    )


@router.get("/nutrition/targets/current")
async def current_target(
    date: str | None = None, current_user: dict = Depends(get_current_user)
):
    return await nutrition_operation(
        nutrition_agent_client.get_current_target(int(current_user["id"]), date)
    )


@router.get("/nutrition/history")
async def daily_history(
    start_date: date,
    end_date: date,
    timezone: str,
    current_user: dict = Depends(get_current_user),
):
    return await nutrition_operation(
        nutrition_agent_client.get_history(
            int(current_user["id"]),
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timezone": timezone,
            },
        )
    )


@router.get("/nutrition/assessment-history")
async def assessment_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    current_user: dict = Depends(get_current_user),
):
    return await nutrition_operation(
        nutrition_agent_client.get_assessment_history(
            int(current_user["id"]), {"limit": limit, "offset": offset}
        )
    )


@router.get("/nutrition/foods", response_model=FoodSearchResponse)
async def search_foods(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    include_usda: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Search shared food reference data; food routes are not user-scoped upstream."""
    try:
        result = await nutrition_agent_client.search_foods(q.strip(), limit, include_usda)
        return FoodSearchResponse.model_validate(result)
    except NutritionAgentError as error:
        raise mapped_nutrition_error(error) from error


@router.get("/nutrition/foods/{fdc_id}", response_model=FoodResponse)
async def get_food(fdc_id: int, current_user: dict = Depends(get_current_user)):
    try:
        return FoodResponse.model_validate(
            await nutrition_agent_client.get_food(fdc_id)
        )
    except NutritionAgentError as error:
        raise mapped_nutrition_error(error) from error


@router.post("/nutrition/meal-plans")
async def meal_plan(
    payload: MealPlanPublicRequest, current_user: dict = Depends(get_current_user)
):
    return await nutrition_operation(
        nutrition_agent_client.generate_meal_plan(
            int(current_user["id"]), payload.model_dump(mode="json")
        )
    )
