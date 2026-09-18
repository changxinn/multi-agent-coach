from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .agent import summarize
from .config import settings
from .schemas import SummarizeRequest, SummarizeResponse

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Private microservice for session summaries.",
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
    return {"status": "healthy", "service": "summarizer"}


@app.post(
    "/v1/summarizer/summarize",
    response_model=SummarizeResponse,
    dependencies=[Depends(require_internal_token)],
)
async def summarize_endpoint(payload: SummarizeRequest) -> SummarizeResponse:
    return summarize(payload)
