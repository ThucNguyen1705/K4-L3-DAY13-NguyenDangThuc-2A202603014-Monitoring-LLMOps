from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_ID_HEADER = "x-request-id"
RESPONSE_TIME_HEADER = "x-response-time-ms"
# Chỉ tin ID đúng format req-<8-hex>; header tùy ý có thể chứa PII hoặc ký tự phá log.
REQUEST_ID_PATTERN = re.compile(r"^req-[0-9a-f]{8}$")


def new_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


def resolve_correlation_id(incoming: str | None) -> str:
    if incoming:
        candidate = incoming.strip().lower()
        if REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
    return new_correlation_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Xóa context của request trước để metadata không rò sang request này.
        clear_contextvars()

        correlation_id = resolve_correlation_id(request.headers.get(REQUEST_ID_HEADER))
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers[REQUEST_ID_HEADER] = correlation_id
        response.headers[RESPONSE_TIME_HEADER] = str(elapsed_ms)

        return response
