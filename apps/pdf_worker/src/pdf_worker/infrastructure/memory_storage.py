from __future__ import annotations


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def put(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:
        self.objects[(bucket, key)] = body

    async def get(self, *, bucket: str, key: str) -> bytes | None:
        return self.objects.get((bucket, key))

    def clear(self) -> None:
        self.objects.clear()
