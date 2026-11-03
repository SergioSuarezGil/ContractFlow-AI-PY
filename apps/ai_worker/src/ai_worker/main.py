from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from contractflow_observability.build_info import version_payload
from contractflow_observability.json_logger import configure_json_logging
from contractflow_observability.llm_metrics import LlmMetrics
from contractflow_observability.metrics import HttpMetricsMiddleware, create_service_metrics
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ai_worker.application.comparison_handler import ComparisonRequestedHandler
from ai_worker.application.comparison_pipeline import ComparisonPipeline
from ai_worker.infrastructure.comparison_store import (
    InMemoryComparisonStore,
    MongoComparisonStore,
)
from ai_worker.infrastructure.event_publisher import NoopEventPublisher, RabbitEventPublisher
from ai_worker.infrastructure.idempotency import InMemoryIdempotencyStore
from ai_worker.infrastructure.llm.factory import create_contract_analyzer
from ai_worker.infrastructure.memory_document_source import InMemoryDocumentSource
from ai_worker.infrastructure.rabbit_consumer import ComparisonRabbitConsumer

logger = logging.getLogger(__name__)

if (os.getenv("LOG_FORMAT") or "").strip().lower() == "json":
    configure_json_logging("ai-worker")

idempotency_store = InMemoryIdempotencyStore()
noop_publisher = NoopEventPublisher()
service_metrics = create_service_metrics("ai-worker")
llm_metrics = LlmMetrics(service_metrics.registry)
_rabbit_publisher: RabbitEventPublisher | None = None
_consumer: ComparisonRabbitConsumer | None = None
_mongo_client: Any = None
_s3_storage: Any = None
_grpc_server: Any = None
document_source: Any = InMemoryDocumentSource()
comparison_store: Any = InMemoryComparisonStore()
pipeline: ComparisonPipeline | None = None
handler: ComparisonRequestedHandler | None = None


def _document_mode() -> str:
    mode = (os.getenv("DOCUMENT_SOURCE") or "").strip().lower()
    if mode:
        return mode
    if os.getenv("CONTRACTS_API_INTERNAL_URL", "").strip():
        return "http"
    return "memory"


def _comparison_store_mode(document_mode: str) -> str:
    mode = (os.getenv("COMPARISON_STORE") or "").strip().lower()
    if mode:
        return mode
    return "mongo" if document_mode == "mongo" else "memory"


async def _mongo_db() -> Any:
    global _mongo_client
    from motor.motor_asyncio import AsyncIOMotorClient

    if _mongo_client is None:
        uri = os.getenv(
            "MONGODB_URI",
            "mongodb://127.0.0.1:27017/contractflow?directConnection=true",
        )
        _mongo_client = AsyncIOMotorClient(uri)
    return _mongo_client[os.getenv("MONGODB_DB", "contractflow")]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _consumer, _rabbit_publisher, document_source, pipeline, handler
    global comparison_store, _s3_storage, _grpc_server, _mongo_client
    document_mode = _document_mode()
    store_mode = _comparison_store_mode(document_mode)
    db = None
    if document_mode == "mongo" or store_mode == "mongo":
        db = await _mongo_db()
    if document_mode == "mongo":
        from contractflow_shared.s3_storage import S3ObjectStorage

        from ai_worker.infrastructure.mongo_document_source import MongoDocumentSource

        _s3_storage = await S3ObjectStorage.connect_from_env()
        document_source = MongoDocumentSource(
            db,
            _s3_storage,
            bucket=os.getenv("S3_BUCKET_DOCUMENTS", "documents"),
        )
        logger.info("Document source ready (Mongo + S3)")
    elif document_mode == "http":
        from ai_worker.infrastructure.http_document_source import HttpDocumentSource

        document_source = HttpDocumentSource()
    else:
        document_source = InMemoryDocumentSource()

    if store_mode == "mongo":
        comparison_store = MongoComparisonStore(db)
    else:
        comparison_store = InMemoryComparisonStore()

    analyzer = create_contract_analyzer()
    pipeline = ComparisonPipeline(document_source, analyzer=analyzer)
    consume = os.getenv("AI_WORKER_CONSUME", "false").lower() in {"1", "true", "yes"}
    messaging = os.getenv("MESSAGING", "noop").lower()
    publisher: Any = noop_publisher
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
    handler = ComparisonRequestedHandler(
        pipeline,
        idempotency_store,
        publisher=publisher,
        comparison_store=comparison_store,
        llm_metrics=llm_metrics,
    )
    if consume and messaging == "rabbit":
        url = os.getenv("RABBITMQ_URL", "").strip()
        _consumer = ComparisonRabbitConsumer(
            url=url,
            handler=handler.handle,
            on_exhausted=handler.publish_terminal_failure,
            exchange_name=os.getenv("RABBITMQ_EXCHANGE", "contractflow.events"),
        )
        await _consumer.start()
        logger.info(
            "Rabbit consumer started (LLM_PROVIDER=%s DOCUMENT_SOURCE=%s)",
            os.getenv("LLM_PROVIDER", "mock"),
            type(document_source).__name__,
        )
    if os.getenv("AI_WORKER_GRPC_ENABLED", "false").lower() in {"1", "true", "yes"}:
        from ai_worker.infrastructure.grpc_server import start_grpc_server

        port = int(os.getenv("AI_WORKER_GRPC_PORT", "50052"))
        _grpc_server = await start_grpc_server(port, comparison_store)
        logger.info("gRPC server listening on %s", port)
    yield
    if _grpc_server is not None:
        await _grpc_server.stop(grace=1)
        _grpc_server = None
    if _consumer is not None:
        await _consumer.stop()
        _consumer = None
    if _rabbit_publisher is not None:
        await _rabbit_publisher.close()
        _rabbit_publisher = None
    if _s3_storage is not None:
        await _s3_storage.close()
        _s3_storage = None
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


app = FastAPI(
    title="ContractFlow AI Worker",
    version="0.1.0",
    description="Extraction + LangChain analyzer (mock|gemini) + event publish",
    lifespan=lifespan,
)
app.add_middleware(HttpMetricsMiddleware, metrics=service_metrics)


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


async def _mongo_check() -> dict[str, str]:
    document_mode = _document_mode()
    needs_mongo = document_mode == "mongo" or _comparison_store_mode(document_mode) == "mongo"
    if not needs_mongo:
        return {"status": "skipped", "message": "memory"}
    try:
        db = await _mongo_db()
        await db.command("ping")
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "message": str(exc)}
    return {"status": "up"}


async def _ready_body() -> tuple[int, dict[str, object]]:
    consume = _flag("AI_WORKER_CONSUME")
    messaging = os.getenv("MESSAGING", "noop").lower()
    checks: dict[str, dict[str, str]] = {"mongodb": await _mongo_check()}
    if messaging == "rabbit" and consume:
        consumer_up = _consumer is not None and _rabbit_publisher is not None
        checks["rabbitmq_consumer"] = {"status": "up" if consumer_up else "down"}
    else:
        checks["rabbitmq_consumer"] = {"status": "skipped", "message": messaging}
    if handler is None or pipeline is None:
        checks["handler"] = {"status": "down", "message": "not started"}
    critical_down = any(
        checks.get(name, {}).get("status") == "down"
        for name in ("mongodb", "rabbitmq_consumer", "handler")
    )
    degraded = any(item["status"] == "down" for item in checks.values())
    body = {
        "status": "degraded" if degraded else "ok",
        "version": version_payload("ai-worker"),
        "checks": checks,
    }
    return (503 if critical_down else 200), body


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "ai-worker",
        "stage": "analyze",
        "llmProvider": (os.getenv("LLM_PROVIDER") or "mock").lower(),
        "documentSource": type(document_source).__name__,
        "consume": os.getenv("AI_WORKER_CONSUME", "false"),
        "grpc": os.getenv("AI_WORKER_GRPC_ENABLED", "false"),
        "version": version_payload("ai-worker"),
    }


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    status_code, body = await _ready_body()
    return JSONResponse(status_code=status_code, content=body)


@app.get("/ready")
async def ready() -> JSONResponse:
    status_code, body = await _ready_body()
    return JSONResponse(status_code=status_code, content=body)


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(service_metrics.registry), media_type=CONTENT_TYPE_LATEST)


def run() -> None:
    import uvicorn

    port = int(os.getenv("AI_WORKER_PORT", "3011"))
    uvicorn.run("ai_worker.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
