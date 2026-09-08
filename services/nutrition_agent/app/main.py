"""Private, token-protected Nutrition Agent API."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .agent import NutritionAgent, _UNSAFE_OUTPUT_TERMS
from .assessment import DISCLAIMER, assess_nutrition, escalation_for, safety_findings
from .config import settings
from .food_reference import FoodReferenceService
from .repository import NutritionRepository
from .schemas import (
    DailyNutritionHistory,
    FoodResponse,
    FoodSearchResponse,
    MealLogCreate,
    MealLogResponse,
    MealPlanRequest,
    MealPlanResponse,
    NutritionEvaluateRequest,
    NutritionEvaluateResponse,
    NutritionProfileResponse,
    NutritionProfileUpsert,
    PaginatedAssessments,
    SafetyFinding,
    TargetCalculateRequest,
    TargetSaveRequest,
    validate_timezone,
)
from .tools.macro_targets import calculate_macro_targets
from .tools.meal_planner import generate_meal_plan
from .tools.tdee_calculator import calculate_tdee

logger = logging.getLogger(__name__)

repository = NutritionRepository(settings)
food_reference = FoodReferenceService(repository, settings.USDA_FDC_API_KEY, settings=settings)
agent = NutritionAgent(settings)

@asynccontextmanager
async def lifespan(_: FastAPI):
    await repository.connect()
    yield
    await repository.close()

app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

async def require_internal_token(x_internal_service_token: Annotated[str | None, Header()] = None) -> None:
    if not settings.NUTRITION_INTERNAL_SERVICE_TOKEN or x_internal_service_token != settings.NUTRITION_INTERNAL_SERVICE_TOKEN:
        raise HTTPException(401, "Invalid internal service token")

def missing(code: str) -> None:
    raise HTTPException(
        404,
        {
            "code": code,
            "message": "The requested nutrition resource was not found.",
        },
    )

def validate_date_range(start_date: date, end_date: date, timezone: str) -> None:
    try:
        validate_timezone(timezone)
    except ValueError as error:
        raise HTTPException(422, "Invalid IANA timezone") from error
    if end_date < start_date or (end_date - start_date).days > 30:
        raise HTTPException(422, "Invalid history date range")

def target_calculation(payload: TargetCalculateRequest) -> dict:
    inputs = payload.inputs
    findings = safety_findings("", inputs.safety_context, inputs)
    referral = escalation_for(findings)
    if referral:
        raise HTTPException(422, {"code": "NUTRITION_SAFETY_REFERRAL_REQUIRED", "message": referral.message})
    expenditure = calculate_tdee(inputs.age, inputs.gender, inputs.weight_kg, inputs.height_cm, inputs.activity_level)
    macros = calculate_macro_targets(expenditure["tdee"], inputs.weight_kg, inputs.fitness_goal, inputs.gender)
    calories = macros.pop("calories")
    findings = safety_findings("", inputs.safety_context, inputs, calories)
    referral = escalation_for(findings)
    if referral:
        raise HTTPException(422, {"code": "NUTRITION_SAFETY_REFERRAL_REQUIRED", "message": referral.message})
    return {"bmr": expenditure["bmr"], "tdee": expenditure["tdee"], "recommended_calories": calories, "macro_targets": macros, "safety_findings": [item.model_dump() for item in findings], "policy_version": "nutrition-safety-v1"}


def _target_context(assessment: NutritionEvaluateResponse, target: dict | None) -> NutritionEvaluateResponse:
    """Attach persisted daily targets and deterministic meal contributions."""
    if not target:
        return assessment
    try:
        inputs = target.get("inputs") or {}
        if isinstance(inputs, str):
            inputs = json.loads(inputs)
        macro_targets = target.get("macro_targets") or {}
        if isinstance(macro_targets, str):
            macro_targets = json.loads(macro_targets)
        tdee = calculate_tdee(
            int(inputs["age"]), inputs["gender"], float(inputs["weight_kg"]),
            float(inputs["height_cm"]), inputs["activity_level"],
        )["tdee"]
        target_values = {"calories": int(target["recommended_calories"]), **macro_targets}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Current nutrition target has incomplete persisted inputs")
        return assessment

    meals = []
    for meal in assessment.meal_recommendations:
        values = {
            "calories": meal.calories,
            "protein_g": meal.protein_g,
            "carbs_g": meal.carbs_g,
            "fat_g": meal.fat_g,
            "fiber_g": meal.fiber_g,
        }
        percentages = {
            nutrient: round(value / float(target_values[nutrient]) * 100)
            for nutrient, value in values.items()
            if target_values.get(nutrient) not in (None, 0)
        }
        meals.append(meal.model_copy(update={"target_percentages": percentages or None}))
    return assessment.model_copy(update={
        "target_available": True,
        "tdee": tdee,
        "macro_targets": macro_targets,
        "meal_recommendations": meals,
    })

@app.get("/health/live")
async def live(): return {"status": "live"}

@app.get("/health/ready")
async def ready():
    """Report sanitized configuration, database, and schema readiness."""
    checks = {"configuration": "failed", "database": "failed", "schema": "failed"}
    if settings.DATABASE_URL and settings.DATABASE_SCHEMA and settings.NUTRITION_INTERNAL_SERVICE_TOKEN:
        checks["configuration"] = "ok"
        try:
            async with repository._pool.acquire() as connection:
                await connection.execute("SELECT 1")
            checks["database"] = "ok"
            try:
                await repository.validate_schema()
                checks["schema"] = "ok"
            except Exception:
                logger.warning("Nutrition Agent readiness schema check failed")
        except Exception:
            logger.warning("Nutrition Agent readiness database check failed")
    return JSONResponse(
        content={"status": "ready", "checks": checks},
        status_code=200 if all(value == "ok" for value in checks.values()) else 503,
    )

@app.get("/health")
async def health(): return await live()

@app.get("/v1/nutrition/users/{user_id}/profile", response_model=NutritionProfileResponse, dependencies=[Depends(require_internal_token)])
async def get_profile(user_id: int):
    value = await repository.get_profile(user_id)
    if not value: missing("NUTRITION_PROFILE_NOT_FOUND")
    return value
@app.put("/v1/nutrition/users/{user_id}/profile", response_model=NutritionProfileResponse, dependencies=[Depends(require_internal_token)])
async def put_profile(user_id: int, payload: NutritionProfileUpsert): return await repository.upsert_profile(user_id, payload)
@app.delete("/v1/nutrition/users/{user_id}/profile", status_code=204, dependencies=[Depends(require_internal_token)])
async def delete_profile(user_id: int):
    if not await repository.delete_profile(user_id): missing("NUTRITION_PROFILE_NOT_FOUND")
    return Response(status_code=204)

@app.post("/v1/nutrition/users/{user_id}/meal-logs", response_model=MealLogResponse, status_code=201, dependencies=[Depends(require_internal_token)])
async def create_meal(user_id: int, payload: MealLogCreate): return await repository.create_meal(user_id, payload)
@app.get("/v1/nutrition/users/{user_id}/meal-logs", dependencies=[Depends(require_internal_token)])
async def list_meals(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    start_date: date | None = None,
    end_date: date | None = None,
    timezone: str | None = None,
):
    date_filter = (start_date, end_date, timezone)
    if any(value is not None for value in date_filter) and not all(date_filter):
        raise HTTPException(422, "start_date, end_date, and timezone are required together")
    if start_date is not None:
        validate_date_range(start_date, end_date, timezone)
    items, total = await repository.list_meals(
        user_id, limit, offset, start_date, end_date, timezone
    )
    return {"items": items, "limit": limit, "offset": offset, "total": total}
@app.get("/v1/nutrition/users/{user_id}/meal-logs/{meal_id}", response_model=MealLogResponse, dependencies=[Depends(require_internal_token)])
async def get_meal(user_id: int, meal_id: int):
    value = await repository.get_meal(user_id, meal_id)
    if not value: missing("MEAL_LOG_NOT_FOUND")
    return value
@app.put("/v1/nutrition/users/{user_id}/meal-logs/{meal_id}", response_model=MealLogResponse, dependencies=[Depends(require_internal_token)])
async def replace_meal(user_id: int, meal_id: int, payload: MealLogCreate):
    value = await repository.replace_meal(user_id, meal_id, payload)
    if not value: missing("MEAL_LOG_NOT_FOUND")
    return value
@app.delete("/v1/nutrition/users/{user_id}/meal-logs/{meal_id}", status_code=204, dependencies=[Depends(require_internal_token)])
async def delete_meal(user_id: int, meal_id: int):
    if not await repository.delete_meal(user_id, meal_id): missing("MEAL_LOG_NOT_FOUND")
    return Response(status_code=204)

@app.post("/v1/nutrition/users/{user_id}/targets/calculate", dependencies=[Depends(require_internal_token)])
async def calculate_targets(user_id: int, payload: TargetCalculateRequest):
    del user_id
    return target_calculation(payload)
@app.post("/v1/nutrition/users/{user_id}/targets", status_code=201, dependencies=[Depends(require_internal_token)])
async def save_target(user_id: int, payload: TargetSaveRequest):
    calculation = target_calculation(payload)
    return await repository.save_target(user_id, payload.inputs.model_dump(mode="json"), calculation, payload.effective_from)
@app.get("/v1/nutrition/users/{user_id}/targets/current", dependencies=[Depends(require_internal_token)])
async def current_target(user_id: int, on_date: date = Query(default_factory=date.today, alias="date")):
    value = await repository.current_target(user_id, on_date)
    if not value: missing("NUTRITION_TARGET_NOT_FOUND")
    return value

@app.get("/v1/nutrition/users/{user_id}/history", response_model=DailyNutritionHistory, dependencies=[Depends(require_internal_token)])
async def daily_history(user_id: int, start_date: date, end_date: date, timezone: str):
    validate_date_range(start_date, end_date, timezone)
    return await repository.daily_history(user_id, start_date, end_date, timezone)

@app.post("/v1/nutrition/users/{user_id}/meal-plans", response_model=MealPlanResponse, dependencies=[Depends(require_internal_token)])
async def meal_plan(user_id: int, payload: MealPlanRequest):
    findings = safety_findings("", payload.safety_context)
    referral = escalation_for(findings)
    if referral:
        raise HTTPException(422, {"code": "NUTRITION_SAFETY_REFERRAL_REQUIRED", "message": referral.message})
    if payload.target_inputs:
        calculation = target_calculation(TargetCalculateRequest(inputs=payload.target_inputs))
        macros = {**calculation["macro_targets"], "calories": calculation["recommended_calories"]}
    else:
        target = await repository.current_target(user_id, datetime.now(UTC).date())
        if not target: missing("NUTRITION_TARGET_NOT_FOUND")
        macros = {**target["macro_targets"], "calories": target["recommended_calories"]}
    profile = await repository.get_profile(user_id)
    if not profile: missing("NUTRITION_PROFILE_NOT_FOUND")
    plan = generate_meal_plan(
        macros,
        profile.dietary_preference,
        profile.meals_per_day,
        allergies=[*profile.allergies, *payload.excluded_foods],
        dietary_restrictions=profile.dietary_restrictions,
    )
    if plan is None:
        no_plan_findings = [SafetyFinding(code="OTHER_MEDICAL_CONDITION", severity="escalate")]
        no_plan_referral = escalation_for(no_plan_findings)
        raise HTTPException(
            422,
            {"code": "NUTRITION_SAFETY_REFERRAL_REQUIRED", "message": no_plan_referral.message},
        )
    meals = [{"meal_type": meal_type, "serving_description": "One serving", **meal} for meal_type, meal in plan["meals"].items()]
    days = [{"date": (payload.start_date or datetime.now(UTC).date()) + timedelta(days=index), "meals": meals} for index in range(payload.days)]
    return MealPlanResponse(days=days, total_calories=plan["total_calories"] * payload.days, total_protein_g=plan["total_protein_g"] * payload.days, total_carbs_g=plan["total_carbs_g"] * payload.days, total_fat_g=plan["total_fat_g"] * payload.days, safety_findings=findings, policy_version="nutrition-safety-v1", disclaimer=DISCLAIMER)

@app.post("/v1/nutrition/users/{user_id}/evaluate", response_model=NutritionEvaluateResponse, dependencies=[Depends(require_internal_token)])
async def evaluate(user_id: int, payload: NutritionEvaluateRequest):
    profile = payload.profile.model_dump(mode="json") if payload.profile else {}
    assessment = assess_nutrition(payload, await repository.history(user_id), profile)
    # Escalations are terminal deterministic safety outcomes. They must never
    # enter the optional presentation/LLM path, which could add advice.
    if assessment.escalation is None:
        if assessment.meal_recommendations:
            assessment = _target_context(
                assessment,
                await repository.current_target(user_id, datetime.now(UTC).date()),
            )
        assessment = agent.present(assessment, payload.message)
    await repository.save_assessment(user_id, assessment)
    return assessment


@app.post("/v1/nutrition/users/{user_id}/evaluate/stream", dependencies=[Depends(require_internal_token)])
async def evaluate_stream(user_id: int, payload: NutritionEvaluateRequest) -> StreamingResponse:
    """Stream a completed, persisted safe assessment's presentation as private SSE."""
    profile = payload.profile.model_dump(mode="json") if payload.profile else {}
    assessment = assess_nutrition(payload, await repository.history(user_id), profile)
    if assessment.escalation is None and assessment.meal_recommendations:
        assessment = _target_context(
            assessment,
            await repository.current_target(user_id, datetime.now(UTC).date()),
        )
    # The final message is persisted before the completion event, matching the
    # non-streaming endpoint's history contract.
    visible_tokens = False

    async def events() -> AsyncIterator[str]:
        nonlocal visible_tokens, assessment
        try:
            if assessment.escalation is not None:
                message = assessment.message
                yield f"event: token\ndata: {json.dumps({'token': message})}\n\n"
                visible_tokens = True
            else:
                parts: list[str] = []
                pending = ""
                holdback = max(len(term) for term in _UNSAFE_OUTPUT_TERMS)
                for token in agent.present_stream(assessment, payload.message):
                    pending += token
                    if any(term in pending.lower() for term in _UNSAFE_OUTPUT_TERMS):
                        raise ValueError("Nutrition LLM stream contained unsafe output")
                    if len(pending) <= holdback:
                        continue
                    safe_token, pending = pending[:-holdback], pending[-holdback:]
                    parts.append(safe_token)
                    yield f"event: token\ndata: {json.dumps({'token': safe_token})}\n\n"
                    visible_tokens = True
                if pending:
                    parts.append(pending)
                    yield f"event: token\ndata: {json.dumps({'token': pending})}\n\n"
                    visible_tokens = True
                final_message = _safe_message_from_stream(assessment, "".join(parts))
                suffix = final_message[len("".join(parts)):]
                if suffix:
                    yield f"event: token\ndata: {json.dumps({'token': suffix})}\n\n"
                    visible_tokens = True
                assessment = assessment.model_copy(update={"message": final_message})
            await repository.save_assessment(user_id, assessment)
            yield f"event: complete\ndata: {assessment.model_dump_json()}\n\n"
        except Exception:
            logger.exception("Nutrition evaluation stream failed after_visible_tokens=%s", visible_tokens)
            if not visible_tokens:
                fallback = assessment.model_copy(update={"message": _safe_message_from_stream(assessment, "")})
                await repository.save_assessment(user_id, fallback)
                yield f"event: token\ndata: {json.dumps({'token': fallback.message})}\n\n"
                yield f"event: complete\ndata: {fallback.model_dump_json()}\n\n"
            else:
                yield "event: error\ndata: {\"code\": \"NUTRITION_STREAM_FAILED\"}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _safe_message_from_stream(assessment: NutritionEvaluateResponse, content: str) -> str:
    """Use the established presentation validator for a complete streamed response."""
    from .agent import _safe_message
    return _safe_message(assessment, content)
@app.get("/v1/nutrition/users/{user_id}/assessment-history", response_model=PaginatedAssessments, dependencies=[Depends(require_internal_token)])
async def assessment_history(user_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000)):
    items, total = await repository.list_assessments(user_id, limit, offset)
    return {"items": items, "limit": limit, "offset": offset, "total": total}
@app.get("/v1/nutrition/foods", response_model=FoodSearchResponse, dependencies=[Depends(require_internal_token)])
async def search_foods(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    include_usda: bool = True,
):
    """Search shared cache data and safely enrich misses through optional USDA."""
    return FoodSearchResponse(**await food_reference.search(q.strip(), limit, include_usda))
@app.get("/v1/nutrition/foods/{fdc_id}", response_model=FoodResponse, dependencies=[Depends(require_internal_token)])
async def get_food(fdc_id: int):
    item = await food_reference.detail(fdc_id)
    if not item: missing("FOOD_NOT_FOUND")
    return FoodResponse(**item)
