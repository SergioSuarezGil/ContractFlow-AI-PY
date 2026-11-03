import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from ai_worker.application.comparison_handler import ComparisonRequestedHandler
from ai_worker.application.comparison_pipeline import ComparisonPipeline
from ai_worker.application.extractor import DocumentExtractor, UnprocessableDocumentError
from ai_worker.application.pii import redact_pii
from ai_worker.application.types import SourceDocument
from ai_worker.infrastructure.event_publisher import NoopEventPublisher
from ai_worker.infrastructure.idempotency import InMemoryIdempotencyStore
from ai_worker.infrastructure.llm.mock_analyzer import MockContractAnalyzer
from ai_worker.infrastructure.memory_document_source import InMemoryDocumentSource


def test_redact_pii_spanish_patterns() -> None:
    text = (
        "Holder 12345678Z IBAN ES7620770024003100251330 "
        "email user@example.com phone 612345678 CUPS ES0021000000000001AA"
    )
    out = redact_pii(text)
    assert "12345678Z" not in out
    assert "user@example.com" not in out
    assert "[REDACTED_DNI]" in out
    assert "[REDACTED_EMAIL]" in out


def test_extract_txt() -> None:
    extractor = DocumentExtractor()
    document = asyncio.run(
        extractor.extract(
            document_id="d1",
            file_name="c.txt",
            role="current",
            content_type="text/plain",
            body=b"Price: 55 monthly",
        )
    )
    assert document.pages[0].text == "Price: 55 monthly"
    assert "d1" in document.full_text


def test_reject_empty_txt() -> None:
    extractor = DocumentExtractor()
    with pytest.raises(UnprocessableDocumentError):
        asyncio.run(
            extractor.extract(
                document_id="d1",
                file_name="empty.txt",
                role="current",
                content_type="text/plain",
                body=b"   ",
            )
        )


def test_pipeline_redacts_and_handler_is_idempotent() -> None:
    source = InMemoryDocumentSource()
    source.put(
        SourceDocument(
            document_id="cur",
            file_name="c.txt",
            role="current",
            content_type="text/plain",
            body=b"Customer 12345678Z Price: 55",
        )
    )
    source.put(
        SourceDocument(
            document_id="prop",
            file_name="p.txt",
            role="proposal",
            content_type="text/plain",
            body=b"Offer email leak@example.com Price: 40",
        )
    )
    store = InMemoryIdempotencyStore()
    publisher = NoopEventPublisher()
    handler = ComparisonRequestedHandler(
        ComparisonPipeline(source, analyzer=MockContractAnalyzer()),
        store,
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

    first = asyncio.run(handler.handle(event))
    assert first is not None
    structured_text = str(first.structured)
    assert "12345678Z" not in structured_text
    assert "leak@example.com" not in structured_text
    assert first.verdict in {"better", "worse", "depends"}
    assert asyncio.run(handler.handle(event)) is None
