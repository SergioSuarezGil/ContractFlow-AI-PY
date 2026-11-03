from __future__ import annotations

from functools import lru_cache

from contractflow_shared import get_settings
from contractflow_shared.s3_storage import S3ObjectStorage
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from contracts_api.application.contracts_service import ContractsService
from contracts_api.application.documents_service import DocumentsService
from contracts_api.application.jobs_service import JobsService
from contracts_api.application.outbox_relay import OutboxRelay
from contracts_api.infrastructure.messaging.noop_publisher import NoopEventPublisher
from contracts_api.infrastructure.messaging.rabbit_publisher import RabbitMqEventPublisher
from contracts_api.infrastructure.messaging.results_consumer import (
    RabbitMqResultsConsumer,
    ResultsEventApplier,
)
from contracts_api.infrastructure.persistence.memory_contract_repository import (
    InMemoryServiceContractRepository,
)
from contracts_api.infrastructure.persistence.memory_document_repository import (
    InMemoryContractDocumentRepository,
)
from contracts_api.infrastructure.persistence.memory_job_repository import (
    InMemoryJobRepository,
)
from contracts_api.infrastructure.persistence.memory_report_repository import (
    InMemoryReportRepository,
)
from contracts_api.infrastructure.persistence.mongo_contract_repository import (
    MongoServiceContractRepository,
)
from contracts_api.infrastructure.persistence.mongo_document_repository import (
    MongoContractDocumentRepository,
)
from contracts_api.infrastructure.persistence.mongo_job_repository import MongoJobRepository
from contracts_api.infrastructure.persistence.mongo_report_repository import (
    MongoReportRepository,
)
from contracts_api.infrastructure.storage.memory_object_storage import (
    InMemoryObjectStorage,
)

_memory_contracts = InMemoryServiceContractRepository()
_memory_documents = InMemoryContractDocumentRepository()
_memory_jobs = InMemoryJobRepository()
_memory_reports = InMemoryReportRepository()
_memory_storage = InMemoryObjectStorage()
_noop_publisher = NoopEventPublisher()
_mongo_client: AsyncIOMotorClient | None = None
_rabbit_publisher: RabbitMqEventPublisher | None = None
_outbox_relay: OutboxRelay | None = None
_results_consumer: RabbitMqResultsConsumer | None = None
_s3_storage: S3ObjectStorage | None = None
_grpc_client: object | None = None


@lru_cache
def get_memory_contract_repository() -> InMemoryServiceContractRepository:
    return _memory_contracts


def get_memory_document_repository() -> InMemoryContractDocumentRepository:
    return _memory_documents


def get_memory_job_repository() -> InMemoryJobRepository:
    return _memory_jobs


def get_memory_report_repository() -> InMemoryReportRepository:
    return _memory_reports


def get_memory_storage() -> InMemoryObjectStorage:
    return _memory_storage


def get_noop_publisher() -> NoopEventPublisher:
    return _noop_publisher


def get_mongo_db() -> AsyncIOMotorDatabase:
    global _mongo_client
    settings = get_settings()
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
    return _mongo_client[settings.mongodb_db]


def get_contract_repository():
    settings = get_settings()
    if settings.contracts_repo == "mongo":
        return MongoServiceContractRepository(get_mongo_db())
    return get_memory_contract_repository()


def get_document_repository():
    settings = get_settings()
    if settings.contracts_repo == "mongo":
        return MongoContractDocumentRepository(get_mongo_db())
    return get_memory_document_repository()


def get_job_repository():
    settings = get_settings()
    if settings.contracts_repo == "mongo":
        return MongoJobRepository(get_mongo_db())
    return get_memory_job_repository()


def get_report_repository():
    settings = get_settings()
    if settings.contracts_repo == "mongo":
        return MongoReportRepository(get_mongo_db())
    return get_memory_report_repository()


def get_object_storage():
    settings = get_settings()
    if settings.object_storage == "s3":
        if _s3_storage is None:
            raise RuntimeError("S3 storage is not initialized")
        return _s3_storage
    return get_memory_storage()


async def startup_persistence() -> None:
    global _s3_storage
    settings = get_settings()
    if settings.object_storage != "s3":
        return
    _s3_storage = await S3ObjectStorage.connect_from_env()
    await _s3_storage.ensure_buckets(
        [settings.s3_bucket_documents, settings.s3_bucket_reports]
    )


async def shutdown_persistence() -> None:
    global _s3_storage, _grpc_client
    if _s3_storage is not None:
        await _s3_storage.close()
        _s3_storage = None
    if _grpc_client is not None:
        close = getattr(_grpc_client, "close", None)
        if close is not None:
            await close()
        _grpc_client = None


def _empty_worker_comparison(job_id: str) -> dict[str, object]:
    return {
        "found": False,
        "jobId": job_id,
        "comparisonId": "",
        "contractId": "",
        "verdict": "",
        "summary": "",
        "createdAt": "",
    }


def get_grpc_client():
    global _grpc_client
    settings = get_settings()
    target = settings.ai_worker_grpc_target.strip()
    if not target:
        return None
    if _grpc_client is None:
        from contracts_api.infrastructure.grpc.ai_worker_grpc_client import AiWorkerGrpcClient

        _grpc_client = AiWorkerGrpcClient(target)
    return _grpc_client


async def lookup_worker_comparison(job_id: str) -> dict[str, object]:
    client = get_grpc_client()
    if client is None:
        return _empty_worker_comparison(job_id)
    return await client.get_by_job_id(job_id)


async def grpc_health_status() -> str:
    client = get_grpc_client()
    if client is None:
        return "disabled"
    result = await client.check()
    return str(result.get("status") or "NOT_SERVING")


def get_results_applier() -> ResultsEventApplier:
    return ResultsEventApplier(get_job_repository(), get_report_repository())


def get_event_publisher():
    settings = get_settings()
    if settings.messaging == "rabbit":
        if _rabbit_publisher is None:
            raise RuntimeError("RabbitMQ publisher not initialized")
        return _rabbit_publisher
    return get_noop_publisher()


def get_contracts_service() -> ContractsService:
    return ContractsService(get_contract_repository())


def get_documents_service() -> DocumentsService:
    settings = get_settings()
    return DocumentsService(
        get_contract_repository(),
        get_document_repository(),
        get_object_storage(),
        documents_bucket=settings.s3_bucket_documents,
    )


def get_jobs_service() -> JobsService:
    return JobsService(get_contract_repository(), get_job_repository())


def get_reports_service():
    from contracts_api.application.reports_service import ReportsService

    settings = get_settings()
    return ReportsService(
        get_job_repository(),
        get_report_repository(),
        get_object_storage(),
        reports_bucket=getattr(settings, "s3_bucket_reports", "reports"),
    )


async def startup_messaging() -> OutboxRelay | None:
    global _rabbit_publisher, _outbox_relay, _results_consumer
    settings = get_settings()
    publisher = get_noop_publisher()
    if settings.messaging == "rabbit":
        _rabbit_publisher = RabbitMqEventPublisher(
            settings.rabbitmq_url, settings.rabbitmq_exchange
        )
        await _rabbit_publisher.connect()
        publisher = _rabbit_publisher
        _results_consumer = RabbitMqResultsConsumer(
            url=settings.rabbitmq_url,
            applier=get_results_applier(),
            exchange_name=settings.rabbitmq_exchange,
        )
        await _results_consumer.start()
    if not settings.outbox_enabled:
        return None
    _outbox_relay = OutboxRelay(
        get_job_repository(),
        publisher,
        interval_ms=settings.outbox_poll_ms,
    )
    _outbox_relay.start()
    return _outbox_relay


async def shutdown_messaging() -> None:
    global _rabbit_publisher, _outbox_relay, _results_consumer
    if _outbox_relay is not None:
        await _outbox_relay.stop()
        _outbox_relay = None
    if _results_consumer is not None:
        await _results_consumer.stop()
        _results_consumer = None
    if _rabbit_publisher is not None:
        await _rabbit_publisher.close()
        _rabbit_publisher = None


def _check(status: str, message: str | None = None) -> dict[str, str]:
    payload = {"status": status}
    if message:
        payload["message"] = message
    return payload


async def mongo_readiness_check() -> dict[str, str]:
    settings = get_settings()
    if settings.contracts_repo != "mongo":
        return _check("skipped", "CONTRACTS_REPO=memory")
    try:
        await get_mongo_db().command("ping")
    except Exception as exc:  # noqa: BLE001
        return _check("down", str(exc))
    return _check("up")


def messaging_readiness() -> dict[str, object]:
    """Legacy boolean snapshot kept for callers that only need connection flags."""
    settings = get_settings()
    checks: dict[str, object] = {
        "messaging": settings.messaging,
        "outboxEnabled": settings.outbox_enabled,
        "outboxRunning": bool(_outbox_relay is not None and _outbox_relay.running),
        "rabbitConnected": _rabbit_publisher is not None,
        "resultsConsumer": _results_consumer is not None,
    }
    ready = True
    if settings.messaging == "rabbit":
        ready = _rabbit_publisher is not None and _results_consumer is not None
    if settings.outbox_enabled:
        ready = ready and bool(_outbox_relay is not None and _outbox_relay.running)
    return {"ready": ready, "checks": checks}


async def nest_readiness(*, grpc_status: str) -> tuple[int, dict[str, object]]:
    """Nest-shaped /health/ready. Critical: Mongo (when configured), Rabbit, outbox."""
    from contractflow_observability.build_info import version_payload

    settings = get_settings()
    checks: dict[str, dict[str, str]] = {
        "mongodb": await mongo_readiness_check(),
    }
    if settings.messaging == "rabbit":
        rabbit_up = _rabbit_publisher is not None and _results_consumer is not None
        checks["rabbitmq"] = _check("up" if rabbit_up else "down")
    else:
        checks["rabbitmq"] = _check("skipped", settings.messaging)

    if settings.outbox_enabled:
        running = bool(_outbox_relay is not None and _outbox_relay.running)
        checks["outbox"] = _check("up" if running else "down")
    else:
        checks["outbox"] = _check("skipped", "disabled")

    if grpc_status in {"disabled", "skipped"}:
        checks["ai-worker-grpc"] = _check("skipped", grpc_status)
    elif grpc_status == "SERVING":
        checks["ai-worker-grpc"] = _check("up")
    else:
        checks["ai-worker-grpc"] = _check("down", grpc_status)

    critical = ("mongodb", "rabbitmq", "outbox")
    critical_down = any(checks[name]["status"] == "down" for name in critical)
    degraded = any(item["status"] == "down" for item in checks.values())
    status = "degraded" if degraded else "ok"
    body: dict[str, object] = {
        "status": status,
        "version": version_payload("contracts-api"),
        "checks": checks,
    }
    return (503 if critical_down else 200), body


# Back-compat alias used by older tests
def get_memory_repository() -> InMemoryServiceContractRepository:
    return get_memory_contract_repository()
