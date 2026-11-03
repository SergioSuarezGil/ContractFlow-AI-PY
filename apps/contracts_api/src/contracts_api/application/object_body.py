from __future__ import annotations

import inspect
from typing import Any


async def read_object(storage: Any, bucket: str, key: str) -> bytes | None:
    """Read bytes from an object storage port (async get_object or sync get)."""
    get_object = getattr(storage, "get_object", None)
    if callable(get_object):
        body = get_object(bucket, key)
        if inspect.isawaitable(body):
            body = await body
        return body
    getter = getattr(storage, "get", None)
    if not callable(getter):
        return None
    body = getter(bucket=bucket, key=key)
    if inspect.isawaitable(body):
        body = await body
    return body
