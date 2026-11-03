from __future__ import annotations

import json
import logging
from typing import Any, Protocol
from uuid import uuid4

import aio_pika

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None: ...


class NoopEventPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None:
        self.published.append((routing_key, envelope))

    def clear(self) -> None:
        self.published.clear()


class RabbitEventPublisher:
    def __init__(self, *, url: str, exchange_name: str = "contractflow.events") -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None:
        if self._exchange is None:
            raise RuntimeError("RabbitEventPublisher not connected")
        body = json.dumps(envelope).encode("utf-8")
        await self._exchange.publish(
            aio_pika.Message(body=body, content_type="application/json", delivery_mode=2),
            routing_key=routing_key,
        )


def build_envelope(
    *,
    event_type: str,
    correlation_id: str,
    household_id: str,
    causation_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from datetime import UTC, datetime

    return {
        "eventId": str(uuid4()),
        "eventType": event_type,
        "schemaVersion": 1,
        "correlationId": correlation_id,
        "causationId": causation_id,
        "householdId": household_id,
        "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }
