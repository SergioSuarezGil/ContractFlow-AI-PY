from __future__ import annotations

from contractflow_observability.metrics import create_service_metrics
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

router = APIRouter(tags=["metrics"])

service_metrics = create_service_metrics("contracts-api")
JOB_TRANSITIONS = Counter(
    "contractflow_job_transitions_total",
    "Job status transitions applied from result events",
    ["event_type"],
    registry=service_metrics.registry,
)


@router.get("/metrics")
def metrics() -> Response:
    return Response(
        generate_latest(service_metrics.registry),
        media_type=CONTENT_TYPE_LATEST,
    )
