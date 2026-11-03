class InMemoryObjectStorage:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    async def put_object(
        self, *, bucket: str, key: str, body: bytes, content_type: str
    ) -> None:
        self._objects[(bucket, key)] = (body, content_type)

    async def get_object(self, bucket: str, key: str) -> bytes | None:
        item = self._objects.get((bucket, key))
        return item[0] if item else None

    async def delete_object(self, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)

    def get(self, bucket: str, key: str) -> bytes | None:
        item = self._objects.get((bucket, key))
        return item[0] if item else None

    def clear(self) -> None:
        self._objects.clear()
