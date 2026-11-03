import asyncio
import json
from typing import Any

from contractflow_shared.rabbit_retry import (
    headers_with_retry,
    is_permanent_ai_error,
    is_transient_results_error,
    retry_count_from_headers,
    should_republish,
)
from contracts_api.domain.errors import ConflictError
from contracts_api.infrastructure.messaging.results_consumer import RabbitMqResultsConsumer


class _Applier:
    def __init__(self) -> None:
        self.calls = 0

    async def apply(self, _payload: dict[str, Any]) -> None:
        self.calls += 1
        raise ConflictError("Job concurrent update conflict")


class _Exchange:
    def __init__(self) -> None:
        self.published: list[tuple[Any, str]] = []

    async def publish(self, message: Any, routing_key: str) -> None:
        self.published.append((message, routing_key))


class _Message:
    def __init__(self, body: bytes, headers: dict | None = None) -> None:
        self.body = body
        self.headers = headers or {}
        self.routing_key = "comparison.completed.v1"
        self.content_type = "application/json"
        self.delivery_mode = 2
        self.correlation_id = None
        self.message_id = None
        self.acked = False
        self.rejected = False
        self.requeue = None

    async def ack(self) -> None:
        self.acked = True

    async def reject(self, requeue: bool = True) -> None:
        self.rejected = True
        self.requeue = requeue


def test_retry_header_math() -> None:
    assert retry_count_from_headers(None) == 0
    assert retry_count_from_headers({"x-retry-count": 2}) == 2
    assert should_republish(2) is True
    assert should_republish(3) is False
    assert headers_with_retry({"kind": "a"}, 1)["x-retry-count"] == 2
    assert is_transient_results_error("Job concurrent update conflict")
    assert is_permanent_ai_error(ValueError("Invalid citation span"))
    assert not is_permanent_ai_error(ConnectionError("broker down"))


def test_results_consumer_republishes_transient_then_dead_letters(monkeypatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "contracts_api.infrastructure.messaging.results_consumer.asyncio.sleep",
        _no_sleep,
    )
    consumer = RabbitMqResultsConsumer(url="amqp://unused", applier=_Applier())
    exchange = _Exchange()
    consumer._exchange = exchange  # type: ignore[assignment]
    body = json.dumps({"eventType": "comparison.completed.v1"}).encode()

    first = _Message(body)
    asyncio.run(consumer._on_message(first))  # type: ignore[arg-type]
    assert first.acked is True
    assert first.rejected is False
    assert exchange.published[0][0].headers["x-retry-count"] == 1

    last = _Message(body, {"x-retry-count": 3})
    asyncio.run(consumer._on_message(last))  # type: ignore[arg-type]
    assert last.rejected is True
    assert last.requeue is False
