from __future__ import annotations

import grpc
from ai_worker.infrastructure.comparison_store import ComparisonStore, lookup_view
from contractflow_grpc import (
    comparison_lookup_pb2,
    comparison_lookup_pb2_grpc,
    worker_health_pb2,
    worker_health_pb2_grpc,
)


class WorkerHealthServicer(worker_health_pb2_grpc.WorkerHealthServicer):
    async def Check(self, request, context):  # noqa: ANN001
        service = (getattr(request, "service", "") or "ai-worker").strip() or "ai-worker"
        return worker_health_pb2.HealthCheckResponse(status="SERVING", service=service)


class ComparisonLookupServicer(comparison_lookup_pb2_grpc.ComparisonLookupServicer):
    def __init__(self, store: ComparisonStore) -> None:
        self._store = store

    async def GetByJobId(self, request, context):  # noqa: ANN001
        job_id = (getattr(request, "job_id", "") or "").strip()
        doc = await self._store.find_by_job_id(job_id) if job_id else None
        view = lookup_view(job_id, doc)
        return comparison_lookup_pb2.ComparisonLookupResponse(
            found=bool(view["found"]),
            job_id=str(view["jobId"]),
            comparison_id=str(view["comparisonId"]),
            contract_id=str(view["contractId"]),
            verdict=str(view["verdict"]),
            summary=str(view["summary"]),
            created_at=str(view["createdAt"]),
        )


async def start_grpc_server(port: int, store: ComparisonStore) -> grpc.aio.Server:
    server = grpc.aio.server()
    worker_health_pb2_grpc.add_WorkerHealthServicer_to_server(WorkerHealthServicer(), server)
    comparison_lookup_pb2_grpc.add_ComparisonLookupServicer_to_server(
        ComparisonLookupServicer(store),
        server,
    )
    server.add_insecure_port(f"0.0.0.0:{port}")
    await server.start()
    return server
