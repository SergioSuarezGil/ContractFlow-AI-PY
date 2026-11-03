from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from ai_worker.application.citation_verifier import verify_citations
from ai_worker.application.comparison_result import ComparisonResult
from ai_worker.application.extraction_pipeline import DocumentSource, ExtractionPipeline
from ai_worker.application.ports import ContractAnalyzerPort
from ai_worker.infrastructure.llm.mock_analyzer import MockContractAnalyzer

DISCLAIMER = (
    "ContractFlow AI analysis is informational only — not legal or financial advice."
)


class ComparisonPipeline:
    def __init__(
        self,
        source: DocumentSource,
        analyzer: ContractAnalyzerPort | None = None,
        extraction: ExtractionPipeline | None = None,
    ) -> None:
        self._extraction = extraction or ExtractionPipeline(source)
        self._analyzer = analyzer or MockContractAnalyzer()

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
    ) -> ComparisonResult:
        bundle = await self._extraction.run(
            job_id=job_id,
            contract_id=contract_id,
            title=title,
            provider_name=provider_name,
            service_type=service_type,
            current_document_ids=current_document_ids,
            proposal_document_ids=proposal_document_ids,
        )
        analyzed = await self._analyzer.analyze(bundle)
        ok, reason = verify_citations(analyzed.structured.citations, bundle.documents)
        if not ok:
            raise ValueError(f"Invalid citation validation: {reason}")

        verdict = analyzed.structured.verdict
        published_verdict = "depends" if verdict == "abstain" else verdict
        return ComparisonResult(
            id=stable_comparison_id(job_id),
            job_id=job_id,
            contract_id=contract_id,
            verdict=published_verdict,  # type: ignore[arg-type]
            summary=analyzed.structured.summary,
            price_notes=analyzed.structured.priceNotes,
            coverage_notes=analyzed.structured.coverageNotes,
            risks=list(analyzed.structured.risks),
            disclaimer=DISCLAIMER,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            analysis_mode=analyzed.meta.provider,
            model_version=analyzed.meta.model,
            prompt_version=analyzed.meta.prompt_version,
            schema_version=analyzed.meta.schema_version,
            citations=[c.model_dump() for c in analyzed.structured.citations],
            structured=analyzed.structured.model_dump(),
            llm_usage={
                "provider": analyzed.meta.provider,
                "model": analyzed.meta.model,
                "inputTokens": analyzed.meta.input_tokens,
                "outputTokens": analyzed.meta.output_tokens,
                "retries": analyzed.meta.retries,
            },
        )


def stable_comparison_id(job_id: str) -> str:
    return hashlib.sha256(f"comparison:{job_id}".encode()).hexdigest()[:32]
