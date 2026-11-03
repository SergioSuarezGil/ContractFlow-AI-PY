from typing import Any


class NoopEventPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None:
        self.published.append((routing_key, envelope))

    def clear(self) -> None:
        self.published.clear()
