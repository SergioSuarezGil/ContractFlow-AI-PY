import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from pdf_worker.application.pdf_generator import MultipagePdfGenerator, PdfReportInput
from pdf_worker.application.report_handler import ReportRequestedHandler
from pdf_worker.infrastructure.memory_storage import InMemoryObjectStorage
from pdf_worker.infrastructure.publisher import NoopEventPublisher


def test_generator_produces_multipage_pdf() -> None:
    pdf = MultipagePdfGenerator().generate(
        PdfReportInput(
            title="Home electricity",
            job_id="j1",
            contract_id="c1",
            verdict="better",
            summary="Proposal is cheaper.",
            price_notes="Delta -15",
            coverage_notes="Green energy",
            disclaimer="Informational only.",
            risks=["Mock analyzer — verify manually"],
            citations=[{"documentId": "p1", "page": 1, "excerpt": "Price: 40 monthly"}],
        )
    )
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page") >= 2 or b"/Count 2" in pdf or pdf.count(b"endobj") > 5


def test_handler_stores_and_publishes_completed() -> None:
    storage = InMemoryObjectStorage()
    publisher = NoopEventPublisher()
    handler = ReportRequestedHandler(storage=storage, publisher=publisher)
    job_id = str(uuid4())
    comparison_id = "cmp1"
    event = {
        "eventId": str(uuid4()),
        "eventType": "report.requested.v1",
        "schemaVersion": 1,
        "correlationId": str(uuid4()),
        "causationId": None,
        "householdId": "hh-a",
        "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": {
            "jobId": job_id,
            "contractId": "c1",
            "ownerId": "o1",
            "comparisonId": comparison_id,
            "comparison": {
                "id": comparison_id,
                "jobId": job_id,
                "contractId": "c1",
                "verdict": "better",
                "summary": "Cheaper proposal",
                "priceNotes": "delta -15",
                "coverageNotes": "ok",
                "risks": ["check"],
                "disclaimer": "info",
                "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "analysisMode": "mock",
            },
        },
    }
    result = asyncio.run(handler.handle(event))
    assert result is not None
    assert result["sizeBytes"] > 0
    assert publisher.published[0][0] == "report.completed.v1"
    assert any(storage.objects.values())
    assert asyncio.run(handler.handle(event)) is None
