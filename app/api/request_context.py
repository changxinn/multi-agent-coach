"""Request-scoped values shared by public API middleware and service clients."""

from __future__ import annotations

from contextvars import ContextVar

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
