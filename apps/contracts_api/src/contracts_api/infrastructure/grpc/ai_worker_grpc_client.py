from __future__ import annotations

import logging

import grpc
from contractflow_grpc import (
    comparison_lookup_pb2,
    comparison_lookup_pb2_grpc,
    worker_health_pb2,
    worker_health_pb2_grpc,
)

logger = logging.getLogger(__name__)


def _empty(job_id: str) -> dict[str, object]:
    return {
        "found": False,
        "jobId": job_id,
        "comparisonId": "",
        "contractId": "",
        "verdict": "",
        "summary": "",
        "createdAt": "",
    }


class AiWorkerGrpcClient:
    """contracts-api → ai-worker client for WorkerHealth and ComparisonLookup."""

    def __init__(self, target: str) -> None:
        self._target = target
        self._channel: grpc.aio.Channel | None = None

    def _channel_or_create(self) -> grpc.aio.Channel:
        if self._channel is None:
            self._channel = grpc.aio.insecure_channel(self._target)
        return self._channel

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

    async def check(self, service: str = "ai-worker") -> dict[str, str]:
        stub = worker_health_pb2_grpc.WorkerHealthStub(self._channel_or_create())
        try:
            response = await stub.Check(
                worker_health_pb2.HealthCheckRequest(service=service),
                timeout=2,
            )
        except grpc.aio.AioRpcError as exc:
            logger.warning("gRPC health check failed: %s", exc)
            return {"status": "NOT_SERVING", "service": service}
        return {"status": response.status or "NOT_SERVING", "service": response.service or service}

    async def get_by_job_id(self, job_id: str) -> dict[str, object]:
        stub = comparison_lookup_pb2_grpc.ComparisonLookupStub(self._channel_or_create())
        try:
            response = await stub.GetByJobId(
                comparison_lookup_pb2.GetComparisonByJobIdRequest(job_id=job_id),
                timeout=3,
            )
        except grpc.aio.AioRpcError as exc:
            logger.warning("gRPC comparison lookup failed: %s", exc)
            return _empty(job_id)
        return {
            "found": bool(response.found),
            "jobId": response.job_id or job_id,
            "comparisonId": response.comparison_id or "",
            "contractId": response.contract_id or "",
            "verdict": response.verdict or "",
            "summary": response.summary or "",
            "createdAt": response.created_at or "",
        }
