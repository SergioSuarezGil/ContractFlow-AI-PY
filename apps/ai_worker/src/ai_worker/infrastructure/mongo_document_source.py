from __future__ import annotations

import logging
from typing import Any

from ai_worker.application.types import SourceDocument

logger = logging.getLogger(__name__)


class MongoDocumentSource:
    """Load document metadata from Mongo and bytes from S3 (TS MongoDocumentLoader)."""

    def __init__(self, db: Any, storage: Any, *, bucket: str) -> None:
        self._db = db
        self._storage = storage
        self._bucket = bucket

    async def load_many(self, document_ids: list[str]) -> list[SourceDocument]:
        out: list[SourceDocument] = []
        for document_id in document_ids:
            doc = await self._db["documents"].find_one({"id": document_id})
            if doc is None:
                logger.warning("Document not found in Mongo: %s", document_id)
                continue
            role = doc.get("role")
            if role not in {"current", "proposal"}:
                raise RuntimeError(f"Invalid document role for {document_id}: {role}")
            storage_key = str(doc.get("storageKey") or "")
            body = await self._storage.get_object(self._bucket, storage_key)
            if body is None:
                raise RuntimeError(f"Empty S3 object for {storage_key}")
            out.append(
                SourceDocument(
                    document_id=str(doc["id"]),
                    file_name=str(doc.get("fileName") or document_id),
                    role=role,
                    content_type=str(doc.get("contentType") or "application/octet-stream"),
                    body=body,
                )
            )
        return out
