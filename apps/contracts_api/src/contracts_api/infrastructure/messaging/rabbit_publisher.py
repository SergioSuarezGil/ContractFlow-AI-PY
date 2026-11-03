from __future__ import annotations

import json
import logging
from typing import Any

import aio_pika

logger = logging.getLogger(__name__)


class RabbitMqEventPublisher:
    def __init__(self, url: str, exchange_name: str = "contractflow.events") -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("RabbitMQ publisher connected to %s", self._exchange_name)

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None:
        if self._exchange is None:
            raise RuntimeError("RabbitMQ publisher is not connected")
        body = json.dumps(envelope).encode("utf-8")
        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=str(envelope.get("eventId", "")),
                correlation_id=str(envelope.get("correlationId", "")),
                type=str(envelope.get("eventType", "")),
            ),
            routing_key=routing_key,
            mandatory=True,
        )
