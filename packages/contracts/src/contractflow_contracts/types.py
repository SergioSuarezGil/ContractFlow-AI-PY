from typing import Any, Literal, TypedDict

KNOWN_EVENT_TYPES = (
    "comparison.requested.v1",
    "comparison.completed.v1",
    "comparison.failed.v1",
    "report.requested.v1",
    "report.completed.v1",
    "report.failed.v1",
)

KnownEventType = Literal[
    "comparison.requested.v1",
    "comparison.completed.v1",
    "comparison.failed.v1",
    "report.requested.v1",
    "report.completed.v1",
    "report.failed.v1",
]


class EventEnvelope(TypedDict):
    eventId: str
    eventType: str
    schemaVersion: Literal[1]
    correlationId: str
    causationId: str | None
    householdId: str
    occurredAt: str
    payload: dict[str, Any]


class ValidateEventOk(TypedDict):
    ok: Literal[True]
    event: EventEnvelope


class ValidateEventErr(TypedDict):
    ok: Literal[False]
    error: str


ValidateEventResult = ValidateEventOk | ValidateEventErr
