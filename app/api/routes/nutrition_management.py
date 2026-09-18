"""Authenticated POST-only Nutrition Management API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.api.schemas.nutrition_management import (
    AssessmentListRequest,
    CurrentTargetRequest,
    DateRangeRequest,
    EmptyRequest,
    FoodSearchRequest,
    MealListRequest,
    MealUpdateRequest,
    MealWriteRequest,
    ProfileWriteRequest,
    ResourceRequest,
    TargetCalculateRequest,
    TargetSaveRequest,
)
from app.db.database import get_db
from app.services.nutrition_management_service import (
    NutritionManagementNotFound,
    NutritionManagementService,
)

router = APIRouter(prefix="/nutrition-management")


def service(db: AsyncSession) -> NutritionManagementService:
    return NutritionManagementService(db)


def missing(code: str) -> HTTPException:
    return HTTPException(404, {"code": code})


@router.post("/profile/get")
async def get_profile(payload: EmptyRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    del payload
    try:
        return await service(db).profile(int(current_user["id"]))
    except NutritionManagementNotFound as error:
        raise missing("NUTRITION_PROFILE_NOT_FOUND") from error


@router.post("/profile/save")
async def save_profile(payload: ProfileWriteRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service(db).save_profile(int(current_user["id"]), payload)


@router.post("/meals/create", status_code=201)
async def create_meal(payload: MealWriteRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service(db).create_meal(int(current_user["id"]), payload)


@router.post("/meals/get")
async def get_meal(payload: ResourceRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await service(db).meal(int(current_user["id"]), payload.id)
    except NutritionManagementNotFound as error:
        raise missing("MEAL_LOG_NOT_FOUND") from error


@router.post("/meals/update")
async def update_meal(payload: MealUpdateRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await service(db).update_meal(int(current_user["id"]), payload.id, MealWriteRequest(**payload.model_dump(exclude={"id"})))
    except NutritionManagementNotFound as error:
        raise missing("MEAL_LOG_NOT_FOUND") from error


@router.post("/meals/delete", status_code=204)
async def delete_meal(payload: ResourceRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        await service(db).delete_meal(int(current_user["id"]), payload.id)
    except NutritionManagementNotFound as error:
        raise missing("MEAL_LOG_NOT_FOUND") from error
    return Response(status_code=204)


@router.post("/meals/list")
async def list_meals(payload: MealListRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service(db).list_meals(int(current_user["id"]), payload.limit, payload.offset, payload.start_date, payload.end_date, payload.timezone)


@router.post("/foods/search")
async def search_foods(payload: FoodSearchRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    del current_user
    return {"items": await service(db).foods(payload.q, payload.limit), "source": "cache_only"}


@router.post("/targets/calculate")
async def calculate_target(payload: TargetCalculateRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    del current_user
    try:
        return service(db).calculate_target(payload)
    except ValueError as error:
        raise HTTPException(422, {"code": "NUTRITION_SAFETY_REFERRAL_REQUIRED", "message": str(error)}) from error


@router.post("/targets/save", status_code=201)
async def save_target(payload: TargetSaveRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await service(db).save_target(int(current_user["id"]), TargetCalculateRequest(inputs=payload.inputs), payload.effective_from)
    except ValueError as error:
        raise HTTPException(422, {"code": "NUTRITION_SAFETY_REFERRAL_REQUIRED", "message": str(error)}) from error


@router.post("/targets/current")
async def current_target(payload: CurrentTargetRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await service(db).current_target(int(current_user["id"]), payload.date)
    except NutritionManagementNotFound as error:
        raise missing("NUTRITION_TARGET_NOT_FOUND") from error


@router.post("/history")
async def history(payload: DateRangeRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service(db).history(int(current_user["id"]), payload.start_date, payload.end_date, payload.timezone)


@router.post("/assessments/list")
async def list_assessments(payload: AssessmentListRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service(db).assessments(int(current_user["id"]), payload.limit, payload.offset)