"""FastAPI entry point for the standalone Recovery Agent service."""

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status

from .agent import RecoveryAgent
from .assessment import assess_recovery
from .chat_inputs import chat_measurements
from .config import settings
from .records import AssessmentInput, CheckInInput, SleepInput
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
    if (
        not settings.INTERNAL_SERVICE_TOKEN
        or x_internal_service_token != settings.INTERNAL_SERVICE_TOKEN
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "recovery-agent"}


@app.post(
    "/v1/recovery/sleep-logs",
    response_model=SleepLogResponse,
    dependencies=[Depends(require_internal_token)],
)
async def create_sleep_log(payload: SleepLogCreate) -> SleepLogResponse:
    row = await repository.create_sleep_log(payload)
    return SleepLogResponse(**dict(row))


@app.post(
    "/v1/recovery/check-ins",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_internal_token)],
)
async def create_checkin(payload: RecoveryCheckInCreate) -> None:
    await repository.create_checkin(payload)


@app.get(
    "/v1/recovery/history/{user_id}",
    response_model=RecoveryHistoryResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_history(user_id: int) -> RecoveryHistoryResponse:
    history = await repository.get_history(user_id)
    return RecoveryHistoryResponse(user_id=user_id, **history.__dict__)


@app.post(
    "/v1/recovery/evaluate",
    response_model=RecoveryEvaluateResponse,
    dependencies=[Depends(require_internal_token)],
)
async def evaluate(payload: RecoveryEvaluateRequest) -> RecoveryEvaluateResponse:
    payload = chat_measurements(payload)
    saved = []
    if payload.sleep_hours is not None and payload.sleep_quality is not None:
        await repository.create_sleep_log(
            SleepLogCreate(
                user_id=payload.user_id,
                duration_minutes=round(payload.sleep_hours * 60),
                quality=payload.sleep_quality,
                notes="Logged during recovery assessment",
            )
        )
        saved.append("sleep log")
    if all(
        value is not None
        for value in (payload.energy, payload.soreness, payload.stress)
    ):
        await repository.create_checkin(
            RecoveryCheckInCreate(
                user_id=payload.user_id,
                energy=payload.energy,
                soreness=payload.soreness,
                stress=payload.stress,
                notes="Logged during recovery assessment",
            )
        )

        saved.append("recovery check-in")

    history = await repository.get_history(payload.user_id)
    assessment = assess_recovery(payload, history)
    assessment = agent.present(assessment, payload.message)
    if saved:
        assessment.message += "\nSaved to Recovery Table: " + " and ".join(saved) + "."
    if payload.sleep_hours is not None and payload.sleep_quality is None:
        assessment.message += "\nTo log sleep, send duration and quality (1-5)."
    if any(
        v is not None for v in (payload.energy, payload.soreness, payload.stress)
    ) and not all(
        v is not None for v in (payload.energy, payload.soreness, payload.stress)
    ):
        assessment.message += (
            "\nTo log a check-in, send energy, soreness and stress (1-10)."
        )
    await repository.save_assessment(payload.user_id, assessment)
    return assessment


@app.get(
    "/v1/recovery/dashboard/{user_id}", dependencies=[Depends(require_internal_token)]
)
async def dashboard(user_id: int, start_date: date, end_date: date):
    if user_id <= 0 or not 0 <= (end_date - start_date).days <= 30:
        raise HTTPException(422, "Invalid user or date range")
    return await repository.dashboard_data(user_id, start_date, end_date)


def register_records(resource, schema):
    async def listing(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        user_id: int | None = Query(None, gt=0),
    ):
        return await repository.list_records(resource, page, page_size, user_id)

    async def write(payload, record_id=None):
        try:
            row = await repository.write_record(
                resource, payload.model_dump(), record_id
            )
        except asyncpg.IntegrityConstraintViolationError as exc:
            raise HTTPException(409, "Invalid recovery record") from exc
        if row is None:
            raise HTTPException(404, "Recovery record not found")
        return row

    async def create(payload: schema):
        return await write(payload)

    async def update(record_id: int, payload: schema):
        return await write(payload, record_id)

    async def delete(record_id: int):
        if not await repository.delete_record(resource, record_id):
            raise HTTPException(404, "Recovery record not found")
        return Response(status_code=204)

    path = "/v1/recovery/records/" + resource
    for suffix, endpoint, method, code in (
        ("", listing, "GET", 200),
        ("", create, "POST", 201),
        ("/{record_id}", update, "PUT", 200),
        ("/{record_id}", delete, "DELETE", 204),
    ):
        app.add_api_route(
            path + suffix,
            endpoint,
            methods=[method],
            status_code=code,
            dependencies=[Depends(require_internal_token)],
        )


register_records("sleep-logs", SleepInput)
register_records("check-ins", CheckInInput)
register_records("assessments", AssessmentInput)
