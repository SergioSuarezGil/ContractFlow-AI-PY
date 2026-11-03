"""S3-compatible object storage (LocalStack / AWS) via aiobotocore."""

from __future__ import annotations

import os
from typing import Any

from botocore.config import Config
from botocore.exceptions import ClientError

_ALREADY_EXISTS = {
    "BucketAlreadyOwnedByYou",
    "BucketAlreadyExists",
    "OperationAborted",
}
_MISSING = {"NoSuchKey", "404", "NotFound", "NoSuchBucket"}


def build_s3_endpoint_url() -> str:
    host = (
        os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT") or "127.0.0.1"
    ).strip()
    port = (os.getenv("S3_PORT") or os.getenv("MINIO_PORT") or "4566").strip()
    use_ssl = (
        os.getenv("S3_USE_SSL") or os.getenv("MINIO_USE_SSL") or "false"
    ).strip().lower() == "true"
    if host.startswith("http://") or host.startswith("https://"):
        return host
    protocol = "https" if use_ssl else "http"
    return f"{protocol}://{host}:{port}"


def _credentials() -> tuple[str, str]:
    access = (os.getenv("S3_ACCESS_KEY") or os.getenv("MINIO_ACCESS_KEY") or "").strip()
    secret = (os.getenv("S3_SECRET_KEY") or os.getenv("MINIO_SECRET_KEY") or "").strip()
    if not access or not secret:
        raise RuntimeError("S3_ACCESS_KEY and S3_SECRET_KEY are required")
    return access, secret


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


class S3ObjectStorage:
    """Async put/get/delete against a path-style S3 endpoint."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._cm: Any | None = None

    @classmethod
    async def connect_from_env(cls) -> S3ObjectStorage:
        import aiobotocore.session

        access, secret = _credentials()
        force_path = (os.getenv("S3_FORCE_PATH_STYLE") or "true").strip().lower() != "false"
        session = aiobotocore.session.get_session()
        cm = session.create_client(
            "s3",
            region_name=(os.getenv("S3_REGION") or "us-east-1").strip(),
            endpoint_url=build_s3_endpoint_url(),
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            config=Config(
                s3={"addressing_style": "path" if force_path else "virtual"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        client = await cm.__aenter__()
        storage = cls(client)
        storage._cm = cm
        return storage

    async def close(self) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)
            self._cm = None

    async def ensure_buckets(self, names: list[str]) -> None:
        for name in names:
            try:
                await self._client.create_bucket(Bucket=name)
            except ClientError as exc:
                if _error_code(exc) not in _ALREADY_EXISTS:
                    raise

    async def put_object(
        self, *, bucket: str, key: str, body: bytes, content_type: str
    ) -> None:
        await self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    async def get_object(self, bucket: str, key: str) -> bytes | None:
        try:
            response = await self._client.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if _error_code(exc) in _MISSING:
                return None
            raise
        payload = response.get("Body")
        if payload is None:
            return b""
        data = await payload.read()
        return bytes(data)

    async def delete_object(self, bucket: str, key: str) -> None:
        try:
            await self._client.delete_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if _error_code(exc) in _MISSING:
                return
            raise
