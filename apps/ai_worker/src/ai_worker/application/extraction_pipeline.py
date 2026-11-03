from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ai_worker.application.extractor import DocumentExtractor
from ai_worker.application.pii import redact_pii
from ai_worker.application.types import (
    ExtractedDocument,
    RedactedExtractedBundle,
    SourceDocument,
)


class DocumentSource(Protocol):
    async def load_many(self, document_ids: list[str]) -> list[SourceDocument]: ...


class ExtractionPipeline:
    def __init__(
        self,
        source: DocumentSource,
        extractor: DocumentExtractor | None = None,
    ) -> None:
        self._source = source
        self._extractor = extractor or DocumentExtractor()

    async def run(
        self,
        *,
        job_id: str,
        contract_id: str,
        title: str,
        provider_name: str,
        service_type: str,
        current_document_ids: list[str],
        proposal_document_ids: list[str],
    ) -> RedactedExtractedBundle:
        ids = [*current_document_ids, *proposal_document_ids]
        sources = await self._source.load_many(ids)
        by_id = {item.document_id: item for item in sources}
        missing = [doc_id for doc_id in ids if doc_id not in by_id]
        if missing:
            raise RuntimeError(f"UNPROCESSABLE: missing documents: {', '.join(missing)}")

        extracted: list[ExtractedDocument] = []
        for doc_id in ids:
            source = by_id[doc_id]
            document = await self._extractor.extract(
                document_id=source.document_id,
                file_name=source.file_name,
                role=source.role,
                content_type=source.content_type,
                body=source.body,
            )
            redacted_pages = [
                replace(page, text=redact_pii(page.text)) for page in document.pages
            ]
            redacted_full = redact_pii(document.full_text)
            extracted.append(
                replace(
                    document,
                    pages=redacted_pages,
                    full_text=redacted_full,
                )
            )

        return RedactedExtractedBundle(
            job_id=job_id,
            contract_id=contract_id,
            title=title,
            provider_name=provider_name,
            service_type=service_type,
            documents=extracted,
        )
