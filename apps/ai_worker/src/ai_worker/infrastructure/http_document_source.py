from __future__ import annotations

import base64
import logging
import os

import httpx
from ai_worker.application.types import SourceDocument

logger = logging.getLogger(__name__)


class HttpDocumentSource:
    """Load document bodies from contracts-api internal endpoint (Docker e2e)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self._base_url = (
            base_url or os.getenv("CONTRACTS_API_INTERNAL_URL", "")
        ).rstrip("/")
        self._token = token or os.getenv("INTERNAL_API_TOKEN", "dev-internal")
        self._timeout_s = timeout_s
        if not self._base_url:
            raise RuntimeError("CONTRACTS_API_INTERNAL_URL is required for HttpDocumentSource")

    async def load_many(self, document_ids: list[str]) -> list[SourceDocument]:
        out: list[SourceDocument] = []
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            for document_id in document_ids:
                response = await client.get(
                    f"{self._base_url}/internal/v1/documents/{document_id}",
                    headers={"X-Internal-Token": self._token},
                )
                if response.status_code == 404:
                    logger.warning("Document not found via API: %s", document_id)
                    continue
                if response.status_code in {401, 403}:
                    raise RuntimeError(
                        f"Unauthorized document fetch for {document_id}: "
                        f"HTTP {response.status_code}"
                    )
                response.raise_for_status()
                payload = response.json()
                role = payload.get("role")
                if role not in {"current", "proposal"}:
                    raise RuntimeError(f"Invalid document role for {document_id}: {role}")
                out.append(
                    SourceDocument(
                        document_id=str(payload["id"]),
                        file_name=str(payload["fileName"]),
                        role=role,
                        content_type=str(payload.get("contentType") or "application/octet-stream"),
                        body=base64.b64decode(payload["bodyBase64"]),
                    )
                )
        return out
