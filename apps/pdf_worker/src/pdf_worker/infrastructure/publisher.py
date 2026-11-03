from __future__ import annotations

import json
from typing import Any

import aio_pika


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
        await self._exchange.publish(
            aio_pika.Message(
                body=json.dumps(envelope).encode("utf-8"),
                content_type="application/json",
                delivery_mode=2,
            ),
            routing_key=routing_key,
        )
