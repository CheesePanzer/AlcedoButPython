import logging
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from alcedo.presentation.exceptions import (
    AlcedoError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
)
from alcedo.presentation.problem_details import ProblemDetails

logger = logging.getLogger("alcedo.presentation")


@dataclass(frozen=True, slots=True)
class ErrorMapping:
    status: int
    title: str


ERROR_MAPPINGS: tuple[tuple[type[BaseException], ErrorMapping], ...] = (
    (NotFoundError, ErrorMapping(404, "Resource Not Found")),
    (UnauthorizedError, ErrorMapping(401, "Unauthorized")),
    (ForbiddenError, ErrorMapping(403, "Forbidden")),
    (BadRequestError, ErrorMapping(400, "Bad Request")),
    (ConflictError, ErrorMapping(409, "Conflict")),
    (TooManyRequestsError, ErrorMapping(429, "Too Many Requests")),
    (RequestValidationError, ErrorMapping(422, "Validation Error")),
    (StaleDataError, ErrorMapping(409, "Conflict")),
    (IntegrityError, ErrorMapping(409, "Conflict")),
    (AlcedoError, ErrorMapping(500, "Business Error")),
)


def add_exception_handlers(
    app: FastAPI,
    *,
    display_sensitive_errors: bool = False,
) -> None:
    async def handle(request: Request, exception: Exception) -> JSONResponse:
        mapping = _mapping_for(exception)
        trace_id = _trace_id(request)
        logger.error(
            "Type=%s Path=%s TraceId=%s Message=%s",
            type(exception).__name__,
            request.url.path,
            trace_id,
            str(exception),
            exc_info=exception,
        )
        problem = _create_problem_details(
            request,
            exception,
            mapping,
            trace_id,
            display_sensitive_errors,
        )
        return JSONResponse(
            status_code=mapping.status,
            content=problem.response_content(),
            media_type="application/problem+json",
        )

    for exception_type, _ in ERROR_MAPPINGS:
        app.add_exception_handler(exception_type, handle)
    app.add_exception_handler(Exception, handle)


def _mapping_for(exception: BaseException) -> ErrorMapping:
    for exception_type, mapping in ERROR_MAPPINGS:
        if isinstance(exception, exception_type):
            return mapping
    return ErrorMapping(500, "Internal Server Error")


def _create_problem_details(
    request: Request,
    exception: Exception,
    mapping: ErrorMapping,
    trace_id: str,
    display_sensitive_errors: bool,
) -> ProblemDetails:
    if isinstance(exception, RequestValidationError):
        detail = " | ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in exception.errors()
        )
    elif isinstance(exception, AlcedoError):
        detail = exception.friendly_message
    elif display_sensitive_errors:
        detail = str(exception)
    elif isinstance(exception, (StaleDataError, IntegrityError)):
        detail = mapping.title
    else:
        detail = "Unhandled Exception"

    extensions: dict[str, str] = {}
    if isinstance(exception, AlcedoError):
        extensions["innerErrorCode"] = exception.code
        if exception.client_action is not None:
            extensions["clientAction"] = exception.client_action

    return ProblemDetails(
        type=f"https://httpstatuses.com/{mapping.status}",
        title=mapping.title,
        status=mapping.status,
        detail=detail,
        instance=request.url.path,
        traceId=trace_id,
        **extensions,
    )


def _trace_id(request: Request) -> str:
    return (
        request.headers.get("traceparent")
        or request.headers.get("x-request-id")
        or uuid4().hex
    )
