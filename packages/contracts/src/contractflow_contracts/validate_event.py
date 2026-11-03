from __future__ import annotations

from typing import Any, cast

from contractflow_contracts.schema_registry import (
    envelope_validator,
    is_known_event_type,
    payload_validators,
)
from contractflow_contracts.types import (
    EventEnvelope,
    KnownEventType,
    ValidateEventResult,
)


def validate_event(raw: Any) -> ValidateEventResult:
    if raw is None or not isinstance(raw, dict):
        return {"ok": False, "error": "Event must be a JSON object"}

    envelope_errors = sorted(envelope_validator().iter_errors(raw), key=lambda e: e.path)
    if envelope_errors:
        first = envelope_errors[0]
        message = first.message
        return {"ok": False, "error": message}

    event_type = raw.get("eventType")
    if not isinstance(event_type, str) or not is_known_event_type(event_type):
        return {"ok": False, "error": f"Unsupported eventType: {event_type}"}

    known = cast(KnownEventType, event_type)
    payload = raw.get("payload")
    payload_errors = sorted(
        payload_validators()[known].iter_errors(payload),
        key=lambda e: e.path,
    )
    if payload_errors:
        return {"ok": False, "error": payload_errors[0].message}

    return {"ok": True, "event": cast(EventEnvelope, raw)}
