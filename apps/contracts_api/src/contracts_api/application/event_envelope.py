from datetime import UTC, datetime
from typing import Any


def create_envelope(
    *,
    event_id: str,
    event_type: str,
    correlation_id: str,
    household_id: str,
    payload: dict[str, Any],
    causation_id: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "eventId": event_id,
        "eventType": event_type,
        "schemaVersion": 1,
        "correlationId": correlation_id,
        "causationId": causation_id,
        "householdId": household_id,
        "occurredAt": (occurred_at or datetime.now(UTC)).isoformat().replace(
            "+00:00", "Z"
        ),
        "payload": payload,
    }
