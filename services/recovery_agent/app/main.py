"""FastAPI entry point for the standalone Recovery Agent service."""
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .assessment import assess_recovery
from .agent import RecoveryAgent
from .config import settings
from .repository import RecoveryRepository
from .schemas import (
    RecoveryCheckInCreate,
    RecoveryEvaluateRequest,
    RecoveryEvaluateResponse,
    RecoveryHistoryResponse,
    SleepLogCreate,
    SleepLogResponse,
)

repository = RecoveryRepository(settings)
agent = RecoveryAgent(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await repository.connect()
    yield
    await repository.close()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Private microservice for recovery coaching assessments.",
    lifespan=lifespan,
)


async def require_internal_token(
    x_internal_service_token: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_service_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal service token")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "recovery-agent"}


@app.post("/v1/recovery/sleep-logs", response_model=SleepLogResponse, dependencies=[Depends(require_internal_token)])
async def create_sleep_log(payload: SleepLogCreate) -> SleepLogResponse:
    row = await repository.create_sleep_log(payload)
    return SleepLogResponse(**dict(row))


@app.post("/v1/recovery/check-ins", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_internal_token)])
async def create_checkin(payload: RecoveryCheckInCreate) -> None:
    await repository.create_checkin(payload)


@app.get("/v1/recovery/history/{user_id}", response_model=RecoveryHistoryResponse, dependencies=[Depends(require_internal_token)])
async def get_history(user_id: int) -> RecoveryHistoryResponse:
    history = await repository.get_history(user_id)
    return RecoveryHistoryResponse(user_id=user_id, **history.__dict__)


@app.post("/v1/recovery/evaluate", response_model=RecoveryEvaluateResponse, dependencies=[Depends(require_internal_token)])
async def evaluate(payload: RecoveryEvaluateRequest) -> RecoveryEvaluateResponse:
    if payload.sleep_hours is not None and payload.sleep_quality is not None:
        await repository.create_sleep_log(
            SleepLogCreate(
                user_id=payload.user_id,
                duration_minutes=round(payload.sleep_hours * 60),
                quality=payload.sleep_quality,
                notes="Logged during recovery assessment",
            )
        )
    if all(value is not None for value in (payload.energy, payload.soreness, payload.stress)):
        await repository.create_checkin(
            RecoveryCheckInCreate(
                user_id=payload.user_id,
                energy=payload.energy,
                soreness=payload.soreness,
                stress=payload.stress,
                notes="Logged during recovery assessment",
            )
        )

    history = await repository.get_history(payload.user_id)
    assessment = assess_recovery(payload, history)
    assessment = agent.present(assessment, payload.message)
    await repository.save_assessment(payload.user_id, assessment)
    return assessment
