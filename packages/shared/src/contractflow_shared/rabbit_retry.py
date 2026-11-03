"""Rabbit retry policy mirrored from the Nest consumers (x-retry-count + backoff)."""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import Any

MAX_RETRIES = 3


class RetryableWorkerError(Exception):
    """Transient worker failure. Retry before publishing a terminal *.failed event."""


def retry_count_from_headers(headers: Mapping[str, Any] | None) -> int:
    if not headers:
        return 0
    raw = headers.get("x-retry-count", 0)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def should_republish(retries: int, *, max_retries: int = MAX_RETRIES) -> bool:
    return retries < max_retries


def backoff_seconds(retries: int) -> float:
    """Same curve as Nest: min(5s, 250ms * 2^retries) plus up to 100ms of jitter."""
    return min(5.0, 0.25 * (2**retries)) + random.random() * 0.1


def headers_with_retry(headers: Mapping[str, Any] | None, retries: int) -> dict[str, Any]:
    merged = dict(headers or {})
    merged["x-retry-count"] = retries + 1
    return merged


def is_transient_results_error(message: str) -> bool:
    return (
        "conflict" in message
        or "ECONNREFUSED" in message
        or "not ready" in message
    )


def is_permanent_ai_error(exc: BaseException) -> bool:
    if type(exc).__name__ in {"UnprocessableDocumentError", "ValidationError"}:
        return True
    message = str(exc)
    return any(
        token in message
        for token in ("UNPROCESSABLE", "Invalid citation", "validation", "Invalid")
    )
