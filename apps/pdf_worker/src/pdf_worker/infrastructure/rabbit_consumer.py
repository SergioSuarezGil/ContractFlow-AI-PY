from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from contractflow_shared.rabbit_retry import (
    backoff_seconds,
    headers_with_retry,
    retry_count_from_headers,
    should_republish,
)

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[Any]]
TerminalFailure = Callable[[dict[str, Any], str], Awaitable[None]]


class ReportRabbitConsumer:
    def __init__(
        self,
        *,
        url: str,
        handler: MessageHandler,
        on_exhausted: TerminalFailure | None = None,
        exchange_name: str = "contractflow.events",
        queue_name: str = "contractflow.pdf.reports",
        prefetch: int = 5,
    ) -> None:
        self._url = url
        self._handler = handler
        self._on_exhausted = on_exhausted
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._prefetch = prefetch
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch)
        exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        self._exchange = exchange
        queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={"x-dead-letter-exchange": "contractflow.events.dlx"},
        )
        await queue.bind(exchange, routing_key="report.requested.v1")
        await queue.consume(self._on_message)

    async def stop(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

    async def _republish(self, message: AbstractIncomingMessage, retries: int) -> None:
        if self._exchange is None:
            raise RuntimeError("Rabbit exchange is not ready")
        await asyncio.sleep(backoff_seconds(retries))
        republished = aio_pika.Message(
            body=message.body,
            headers=headers_with_retry(message.headers, retries),
            content_type=message.content_type,
            delivery_mode=message.delivery_mode or aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=message.correlation_id,
            message_id=message.message_id,
        )
        await self._exchange.publish(republished, routing_key=message.routing_key or "")

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Rejecting non-JSON message")
            await message.reject(requeue=False)
            return
        if not isinstance(payload, dict):
            await message.reject(requeue=False)
            return
        try:
            await self._handler(payload)
        except Exception as exc:  # noqa: BLE001
            text = str(exc)
            if "Invalid event" in text:
                logger.error("Permanent failure: %s", text)
                await message.reject(requeue=False)
                return
            retries = retry_count_from_headers(message.headers)
            if should_republish(retries):
                logger.warning("Retrying report (%s/3): %s", retries + 1, text)
                await self._republish(message, retries)
                await message.ack()
                return
            logger.error("Report retries exhausted: %s", text)
            if self._on_exhausted is not None:
                try:
                    await self._on_exhausted(payload, text)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to publish report.failed.v1")
            await message.reject(requeue=False)
            return
        await message.ack()
