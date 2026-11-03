from __future__ import annotations

from contractflow_shared.s3_storage import S3ObjectStorage


class S3ReportStorage:
    """pdf-worker object port backed by the shared S3 adapter."""

    def __init__(self, storage: S3ObjectStorage) -> None:
        self._storage = storage

    async def put(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:
        await self._storage.put_object(
            bucket=bucket,
            key=key,
            body=body,
            content_type=content_type,
        )
