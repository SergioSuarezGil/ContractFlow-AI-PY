import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from ai_worker.application.comparison_handler import ComparisonRequestedHandler
from ai_worker.application.comparison_pipeline import ComparisonPipeline
from ai_worker.application.contract_analysis_schema import ContractAnalysisStructured
from ai_worker.application.money_comparison import verdict_from_prices
from ai_worker.application.types import SourceDocument
from ai_worker.infrastructure.event_publisher import NoopEventPublisher
from ai_worker.infrastructure.idempotency import InMemoryIdempotencyStore
from ai_worker.infrastructure.llm.mock_analyzer import MockContractAnalyzer
from ai_worker.infrastructure.memory_document_source import InMemoryDocumentSource


def test_verdict_from_prices_prefers_cheaper_proposal() -> None:
    structured = ContractAnalysisStructured(
        verdict="depends",
        periodicity="monthly",
        currentPrice=55,
        proposalPrice=40,
        summary="x",
    )
    assert verdict_from_prices(structured) == "better"


def test_mock_analyzer_and_handler_publish_events() -> None:
    source = InMemoryDocumentSource()
    source.put(
        SourceDocument(
            document_id="cur",
            file_name="c.txt",
            role="current",
            content_type="text/plain",
            body=b"Price: 55 monthly electricity",
        )
    )
    source.put(
        SourceDocument(
            document_id="prop",
            file_name="p.txt",
            role="proposal",
            content_type="text/plain",
            body=b"Price: 40 monthly\ncoverage: green energy\nPenalty: none",
        )
    )
    publisher = NoopEventPublisher()
    handler = ComparisonRequestedHandler(
        ComparisonPipeline(source, analyzer=MockContractAnalyzer()),
        InMemoryIdempotencyStore(),
        publisher=publisher,
    )
    job_id = str(uuid4())
    event = {
        "eventId": str(uuid4()),
        "eventType": "comparison.requested.v1",
        "schemaVersion": 1,
        "correlationId": str(uuid4()),
        "causationId": None,
        "householdId": "hh-a",
        "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": {
            "jobId": job_id,
            "contractId": "c1",
            "ownerId": "o1",
            "currentDocumentIds": ["cur"],
            "proposalDocumentIds": ["prop"],
            "title": "Home",
            "providerName": "Acme",
            "serviceType": "electricity",
        },
    }
    result = asyncio.run(handler.handle(event))
    assert result is not None
    assert result.verdict == "better"
    assert result.analysis_mode == "mock"
    assert any(c.get("excerpt") for c in result.citations)
    keys = [k for k, _ in publisher.published]
    assert keys == ["comparison.completed.v1", "report.requested.v1"]
    assert asyncio.run(handler.handle(event)) is None
