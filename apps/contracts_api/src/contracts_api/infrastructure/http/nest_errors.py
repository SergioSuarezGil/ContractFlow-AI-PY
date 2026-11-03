from __future__ import annotations

from typing import Any

_STATUS_ERROR = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


def nest_http_error(status_code: int, message: Any, error: str | None = None) -> dict[str, Any]:
    """Nest default HttpException JSON: statusCode, error, message."""
    return {
        "statusCode": status_code,
        "error": error or _STATUS_ERROR.get(status_code, "Error"),
        "message": message,
    }


def nest_domain_error(status_code: int, exc: BaseException) -> dict[str, Any]:
    """Nest DomainExceptionFilter uses the exception class name as `error`."""
    return nest_http_error(status_code, str(exc), error=type(exc).__name__)
