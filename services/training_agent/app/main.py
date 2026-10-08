from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import close_db, get_db, init_db
from .schemas import (
    AdaptRequest,
    ChatRequest,
    ChatResponse,
    DailyWorkoutRequest,
    ExerciseLookupRequest,
    ExerciseSearchRequest,
    ProgramGenerateRequest,
    ProgramListRequest,
    ProgressRequest,
    TrainingPreferencesRequest,
    TrainingProfileRequest,
    UserRequest,
    WorkoutListRequest,
    WorkoutLogRequest,
)
from .service import TrainingService

app = FastAPI(title=settings.APP_NAME, version="1.0.0")


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


def get_service(db: AsyncSession = Depends(get_db)) -> TrainingService:
    return TrainingService(db)


Service = Annotated[TrainingService, Depends(get_service)]


@app.on_event("startup")
async def startup() -> None:
    if settings.RUN_MIGRATIONS:
        await init_db()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "training-agent"}


@app.post(
    "/v1/training/exercises/search", dependencies=[Depends(require_internal_token)]
)
async def exercise_search(payload: ExerciseSearchRequest, service: Service):
    return {"items": await service.exercise_guidance(payload.query)}


@app.post(
    "/v1/training/exercises/lookup", dependencies=[Depends(require_internal_token)]
)
async def exercise_lookup(payload: ExerciseLookupRequest, service: Service):
    items = await service.exercises(payload.query)
    if not items:
        return {
            "name": payload.query,
            "guidance": "Start light, use a controlled pain-free range, and progress gradually.",
        }
    return items[0]


@app.post(
    "/v1/training/programs/generate", dependencies=[Depends(require_internal_token)]
)
async def generate_program(payload: ProgramGenerateRequest, service: Service):
    try:
        return await service.generate_program(payload.user_id, payload.recovery_status)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post(
    "/v1/training/programs/list", dependencies=[Depends(require_internal_token)]
)
async def list_programs(payload: ProgramListRequest, service: Service):
    return {"items": await service.list_programs(payload.user_id)}


@app.post("/v1/training/workouts/log", dependencies=[Depends(require_internal_token)])
async def log_workout(
    payload: WorkoutLogRequest,
    service: Service,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    try:
        return await service.log_workout(payload, idempotency_key)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/v1/training/workouts/list", dependencies=[Depends(require_internal_token)])
async def list_workouts(payload: WorkoutListRequest, service: Service):
    return {"items": await service.list_workouts(payload.user_id, payload.days, payload.limit)}


@app.post("/v1/training/progress", dependencies=[Depends(require_internal_token)])
async def progress(payload: ProgressRequest, service: Service):
    return await service.progress(payload.user_id, payload.days)


@app.post("/v1/training/programs/adapt", dependencies=[Depends(require_internal_token)])
async def adapt_program(payload: AdaptRequest, service: Service):
    try:
        return await service.generate_program(payload.user_id, payload.recovery_status, payload.reason)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/v1/training/daily-workout", dependencies=[Depends(require_internal_token)])
async def daily_workout(payload: DailyWorkoutRequest, service: Service):
    return await service.daily_workout(payload)


@app.post("/v1/training/profile/get", dependencies=[Depends(require_internal_token)])
async def get_profile(payload: UserRequest, service: Service):
    return await service.profile(payload.user_id)


@app.post("/v1/training/profile/update", dependencies=[Depends(require_internal_token)])
async def update_profile(payload: TrainingProfileRequest, service: Service):
    return await service.save_profile(payload)


@app.post("/v1/training/preferences/get", dependencies=[Depends(require_internal_token)])
async def get_preferences(payload: UserRequest, service: Service):
    return await service.preferences(payload.user_id)


@app.post("/v1/training/preferences/update", dependencies=[Depends(require_internal_token)])
async def update_preferences(payload: TrainingPreferencesRequest, service: Service):
    return await service.save_preferences(payload)


@app.post("/v1/training/context", dependencies=[Depends(require_internal_token)])
async def training_context(payload: UserRequest, service: Service):
    return await service.context(payload.user_id)


@app.post(
    "/v1/training/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_internal_token)],
)
async def chat(payload: ChatRequest, service: Service):
    latest = next(
        message.content
        for message in reversed(payload.messages)
        if message.role == "user"
    )
    matches = await service.exercises(latest)
    if matches:
        return ChatResponse(
            message=f"{matches[0]['name'].title()}: {matches[0]['guidance']}",
            tool_trace=["exercise_lookup"],
        )
    return ChatResponse(
        message="I can help build a safe program, explain exercise form, and track training. What goal, training experience, equipment, and weekly availability should I use?",
        tool_trace=[],
    )
