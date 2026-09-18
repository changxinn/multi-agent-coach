from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .agent import route
from .config import settings
from .schemas import RouteRequest, RouteResponse

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Private microservice for Head Coach routing decisions.",
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
    return {"status": "healthy", "service": "head-coach"}


@app.post(
    "/v1/head-coach/route",
    response_model=RouteResponse,
    dependencies=[Depends(require_internal_token)],
)
async def route_endpoint(payload: RouteRequest) -> RouteResponse:
    return route(payload)
