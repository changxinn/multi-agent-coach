"""Authenticated frontend CRUD backed by the private Recovery Agent database."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.routes.auth import get_current_user
from app.services.recovery_agent_client import (
    RecoveryAgentUnavailableError,
    RecoveryRecordError,
    recovery_agent_client,
)


class RecoveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)


class SleepInput(RecoveryInput):
    duration_minutes: int = Field(ge=0, le=1440)
    quality: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class CheckInInput(RecoveryInput):
    energy: int = Field(ge=1, le=10)
    soreness: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    notes: str | None = Field(default=None, max_length=1000)


class AssessmentInput(RecoveryInput):
    status: Literal["green", "amber", "red", "escalate"]
    score: int = Field(ge=0)
    response: dict[str, Any]
    tool_trace: list[str]


router = APIRouter(prefix="/recovery", dependencies=[Depends(get_current_user)])


async def remote(call):
    try:
        return await call
    except RecoveryRecordError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except RecoveryAgentUnavailableError as exc:
        raise HTTPException(503, "Recovery service is unavailable") from exc


def register_crud(resource, schema):
    async def listing(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        user_id: int | None = Query(None, gt=0),
    ):
        return await remote(
            recovery_agent_client.list_records(resource, page, page_size, user_id)
        )

    async def create(payload: schema):
        return await remote(
            recovery_agent_client.write_record(resource, payload.model_dump())
        )

    async def update(record_id: int, payload: schema):
        return await remote(
            recovery_agent_client.write_record(
                resource, payload.model_dump(), record_id
            )
        )

    async def delete(record_id: int):
        await remote(recovery_agent_client.delete_record(resource, record_id))
        return Response(status_code=204)

    path = "/" + resource
    router.add_api_route(path, listing, methods=["GET"])
    router.add_api_route(path, create, methods=["POST"], status_code=201)
    router.add_api_route(path + "/{record_id}", update, methods=["PUT"])
    router.add_api_route(
        path + "/{record_id}", delete, methods=["DELETE"], status_code=204
    )


register_crud("sleep-logs", SleepInput)
register_crud("check-ins", CheckInInput)
register_crud("assessments", AssessmentInput)
