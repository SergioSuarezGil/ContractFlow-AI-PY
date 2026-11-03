import asyncio

from botocore.exceptions import ClientError
from contractflow_shared.s3_storage import S3ObjectStorage, build_s3_endpoint_url


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _FakeS3:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.objects: dict[tuple[str, str], bytes] = {}

    async def create_bucket(self, *, Bucket: str) -> None:
        if Bucket in self.buckets:
            raise ClientError(
                {"Error": {"Code": "BucketAlreadyOwnedByYou", "Message": "exists"}},
                "CreateBucket",
            )
        self.buckets.add(Bucket)

    async def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[(Bucket, Key)] = Body

    async def get_object(self, *, Bucket: str, Key: str) -> dict:
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject")
        return {"Body": _Body(self.objects[(Bucket, Key)])}

    async def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


def test_s3_roundtrip_and_missing() -> None:
    storage = S3ObjectStorage(_FakeS3())

    async def _run() -> None:
        await storage.ensure_buckets(["documents"])
        await storage.ensure_buckets(["documents"])
        await storage.put_object(
            bucket="documents",
            key="hh/c/d",
            body=b"hello",
            content_type="text/plain",
        )
        assert await storage.get_object("documents", "hh/c/d") == b"hello"
        assert await storage.get_object("documents", "missing") is None
        await storage.delete_object("documents", "hh/c/d")
        assert await storage.get_object("documents", "hh/c/d") is None

    asyncio.run(_run())


def test_endpoint_url_adds_scheme(monkeypatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT", "object-storage")
    monkeypatch.setenv("S3_PORT", "4566")
    monkeypatch.setenv("S3_USE_SSL", "false")
    assert build_s3_endpoint_url() == "http://object-storage:4566"
