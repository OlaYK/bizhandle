import json
import logging
import time
import traceback
from contextvars import ContextVar
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("monidesk.api")


def setup_observability() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def get_request_id() -> str:
    return request_id_ctx.get()


def _error_response(
    *,
    status_code: int,
    request: Request,
    code: str,
    message: str,
    details: list[dict] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("x-request-id")
        or get_request_id()
    )
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "path": request.url.path,
                "details": details,
            }
        },
    )


async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
        )
        request_id_ctx.reset(token)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-API-Timeout-Hint-Ms"] = str(settings.api_timeout_hint_ms)
    return response


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("x-request-id")
        or get_request_id()
    )
    logger.error(
        json.dumps(
            {
                "event": "unhandled_exception",
                "request_id": request_id,
                "path": request.url.path,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=10),
            }
        )
    )
    return _error_response(
        status_code=500,
        request=request,
        code="internal_error",
        message="Internal server error",
    )


_STATUS_CODE_MAP = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


async def http_exception_handler(request: Request, exc: HTTPException):
    code = _STATUS_CODE_MAP.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    details = None if isinstance(exc.detail, str) else exc.detail
    return _error_response(
        status_code=exc.status_code,
        request=request,
        code=code,
        message=message,
        details=details,
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        location = [str(part) for part in err.get("loc", []) if part != "body"]
        details.append(
            {
                "field": ".".join(location) if location else "body",
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type"),
            }
        )

    return _error_response(
        status_code=422,
        request=request,
        code="validation_error",
        message="Validation failed",
        details=details,
    )
