from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from contractflow_observability.build_info import version_payload
from contractflow_observability.json_logger import configure_json_logging
from contractflow_observability.metrics import HttpMetricsMiddleware, create_service_metrics
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from pdf_worker.application.report_handler import ReportRequestedHandler
from pdf_worker.infrastructure.api_report_uploader import ApiReportUploader
from pdf_worker.infrastructure.memory_storage import InMemoryObjectStorage
from pdf_worker.infrastructure.publisher import NoopEventPublisher, RabbitEventPublisher
from pdf_worker.infrastructure.rabbit_consumer import ReportRabbitConsumer

logger = logging.getLogger(__name__)

if (os.getenv("LOG_FORMAT") or "").strip().lower() == "json":
    configure_json_logging("pdf-worker")

service_metrics = create_service_metrics("pdf-worker")
storage = InMemoryObjectStorage()
_s3_storage: Any = None
noop_publisher = NoopEventPublisher()
handler: ReportRequestedHandler | None = None
_rabbit_publisher: RabbitEventPublisher | None = None
_consumer: ReportRabbitConsumer | None = None


def _storage_mode() -> str:
    return (os.getenv("PDF_STORAGE") or os.getenv("OBJECT_STORAGE") or "memory").strip().lower()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _consumer, _rabbit_publisher, handler, storage, _s3_storage
    consume = os.getenv("PDF_WORKER_CONSUME", "false").lower() in {"1", "true", "yes"}
    messaging = os.getenv("MESSAGING", "noop").lower()
    publisher = noop_publisher
    uploader = ApiReportUploader()
    if _storage_mode() == "s3":
        from contractflow_shared.s3_storage import S3ObjectStorage

        from pdf_worker.infrastructure.s3_report_storage import S3ReportStorage

        _s3_storage = await S3ObjectStorage.connect_from_env()
        bucket = os.getenv("S3_BUCKET_REPORTS", "reports")
        await _s3_storage.ensure_buckets([bucket])
        storage = S3ReportStorage(_s3_storage)
        logger.info("PDF object storage ready (S3 bucket=%s)", bucket)
    else:
        storage = InMemoryObjectStorage()
    if messaging == "rabbit":
        url = os.getenv("RABBITMQ_URL", "").strip()
        if not url:
            raise RuntimeError("RABBITMQ_URL is required when MESSAGING=rabbit")
        _rabbit_publisher = RabbitEventPublisher(
            url=url,
            exchange_name=os.getenv("RABBITMQ_EXCHANGE", "contractflow.events"),
        )
        await _rabbit_publisher.connect()
        publisher = _rabbit_publisher
    handler = ReportRequestedHandler(
        storage=storage,
        publisher=publisher,
        bucket=os.getenv("S3_BUCKET_REPORTS", "reports"),
        uploader=uploader if uploader.enabled else None,
    )
    if consume and messaging == "rabbit":
        _consumer = ReportRabbitConsumer(
            url=os.getenv("RABBITMQ_URL", "").strip(),
            handler=handler.handle,
            on_exhausted=handler.publish_terminal_failure,
            exchange_name=os.getenv("RABBITMQ_EXCHANGE", "contractflow.events"),
        )
        await _consumer.start()
        logger.info(
            "PDF worker consumer started (apiUpload=%s storage=%s)",
            "on" if uploader.enabled else "off",
            _storage_mode(),
        )
    yield
    if _s3_storage is not None:
        await _s3_storage.close()
        _s3_storage = None
    if _consumer is not None:
        await _consumer.stop()
        _consumer = None
    if _rabbit_publisher is not None:
        await _rabbit_publisher.close()
        _rabbit_publisher = None


app = FastAPI(
    title="ContractFlow PDF Worker",
    version="0.1.0",
    description="Multipage PDF report generation",
    lifespan=lifespan,
)
app.add_middleware(HttpMetricsMiddleware, metrics=service_metrics)


def _ready_body() -> tuple[int, dict[str, object]]:
    consume = os.getenv("PDF_WORKER_CONSUME", "false").lower() in {"1", "true", "yes"}
    messaging = os.getenv("MESSAGING", "noop").lower()
    checks: dict[str, dict[str, str]] = {}
    if messaging == "rabbit" and consume:
        consumer_up = _consumer is not None and _rabbit_publisher is not None
        checks["rabbitmq_consumer"] = {"status": "up" if consumer_up else "down"}
    else:
        checks["rabbitmq_consumer"] = {"status": "skipped", "message": messaging}
    if handler is None:
        checks["handler"] = {"status": "down"}
    critical_down = any(item["status"] == "down" for item in checks.values())
    body = {
        "status": "degraded" if critical_down else "ok",
        "version": version_payload("pdf-worker"),
        "checks": checks,
    }
    return (503 if critical_down else 200), body


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "pdf-worker",
        "consume": os.getenv("PDF_WORKER_CONSUME", "false"),
        "storage": _storage_mode(),
        "version": version_payload("pdf-worker"),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(service_metrics.registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    status_code, body = _ready_body()
    return JSONResponse(status_code=status_code, content=body)


@app.get("/ready")
def ready() -> JSONResponse:
    status_code, body = _ready_body()
    return JSONResponse(status_code=status_code, content=body)


def run() -> None:
    import uvicorn

    port = int(os.getenv("PDF_WORKER_PORT", "3012"))
    uvicorn.run("pdf_worker.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
