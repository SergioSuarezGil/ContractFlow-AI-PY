from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ApiReportUploader:
    """Push generated PDF bytes to contracts-api internal store (memory/S3 bridge)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = (
            base_url or os.getenv("CONTRACTS_API_INTERNAL_URL", "")
        ).rstrip("/")
        self._token = token or os.getenv("INTERNAL_API_TOKEN", "dev-internal")
        self._timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self._base_url)

    async def upload(
        self,
        *,
        report_id: str,
        job_id: str,
        contract_id: str,
        owner_id: str,
        household_id: str,
        comparison_id: str,
        storage_key: str,
        file_name: str,
        content_type: str,
        body: bytes,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload = {
            "jobId": job_id,
            "contractId": contract_id,
            "ownerId": owner_id,
            "householdId": household_id,
            "comparisonId": comparison_id,
            "fileName": file_name,
            "contentType": content_type,
            "storageKey": storage_key,
            "bodyBase64": base64.b64encode(body).decode("ascii"),
        }
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.put(
                f"{self._base_url}/internal/v1/reports/{report_id}",
                headers={"X-Internal-Token": self._token},
                json=payload,
            )
            response.raise_for_status()
            logger.info("Uploaded report %s to contracts-api (%s bytes)", report_id, len(body))
            return response.json()
