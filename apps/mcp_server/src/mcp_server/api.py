from __future__ import annotations

import os

import httpx


def api_base() -> str:
    return (os.getenv("CONTRACTFLOW_API_BASE") or "http://127.0.0.1:3010").rstrip("/")


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    bearer = (os.getenv("CONTRACTFLOW_BEARER_TOKEN") or "").strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    owner = (os.getenv("CONTRACTFLOW_OWNER_ID") or "").strip()
    household = (os.getenv("CONTRACTFLOW_HOUSEHOLD_ID") or "").strip()
    if owner:
        headers["X-Owner-Id"] = owner
    if household:
        headers["X-Household-Id"] = household
    return headers


async def compare_contracts(contract_id: str, client: httpx.AsyncClient | None = None) -> str:
    """POST /api/v1/contracts/{id}/comparisons and return the response body."""
    return await _request(
        "POST",
        f"/api/v1/contracts/{contract_id}/comparisons",
        client,
    )


async def get_comparison_job(job_id: str, client: httpx.AsyncClient | None = None) -> str:
    """GET /api/v1/jobs/{id} and return the response body."""
    return await _request("GET", f"/api/v1/jobs/{job_id}", client)


async def _request(method: str, path: str, client: httpx.AsyncClient | None) -> str:
    owns_client = client is None
    http = client or httpx.AsyncClient(base_url=api_base(), timeout=30.0)
    try:
        response = await http.request(method, path, headers=_headers())
        text = response.text
        if response.is_error:
            raise RuntimeError(f"HTTP {response.status_code}: {text}")
        return text
    finally:
        if owns_client:
            await http.aclose()
