from __future__ import annotations

import re

from ai_worker.application.contract_analysis_schema import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    AnalysisCitation,
    ContractAnalysisStructured,
)
from ai_worker.application.money_comparison import verdict_from_prices
from ai_worker.application.ports import AnalyzerRunMeta, ContractAnalyzerResult
from ai_worker.application.types import RedactedExtractedBundle

MODEL = "mock-contract-analyzer-v1"
_INJECTION = re.compile(
    r"ignore (all )?previous instructions|send (data|secrets) to http",
    re.IGNORECASE,
)


class MockContractAnalyzer:
    async def analyze(self, bundle: RedactedExtractedBundle) -> ContractAnalyzerResult:
        current = [d for d in bundle.documents if d.role == "current"]
        proposal = [d for d in bundle.documents if d.role == "proposal"]

        if any(_INJECTION.search(d.full_text) for d in bundle.documents):
            structured = ContractAnalysisStructured(
                verdict="abstain",
                summary="Abstaining due to suspicious instruction-like content in documents.",
                priceNotes="Not computed.",
                coverageNotes="Not computed.",
                risks=["Potential prompt injection patterns detected in source text"],
                unknownFields=["all pricing fields"],
            )
            return self._wrap(structured, 0)

        if not current or not proposal:
            structured = ContractAnalysisStructured(
                verdict="abstain",
                summary="Insufficient documents to compare current vs proposal.",
                risks=["Missing current or proposal document"],
            )
            return self._wrap(structured, 0)

        current_price = _extract_price(current[0].full_text)
        proposal_price = _extract_price(proposal[0].full_text)
        permanence = _extract_permanence(proposal[0].full_text)
        penalty = _extract_line(proposal[0].full_text, r"penalty[:\s]+([^\n]+)")
        contradiction = (
            re.search(r"contradiction", proposal[0].full_text, re.I) is not None
            and re.search(r"no permanence", proposal[0].full_text, re.I) is not None
            and permanence is not None
            and permanence > 0
        )

        base_verdict: str = "depends"
        if contradiction:
            base_verdict = "abstain"
        elif current_price is not None and proposal_price is not None:
            if proposal_price < current_price:
                base_verdict = "better"
            elif proposal_price > current_price:
                base_verdict = "worse"

        citation_doc = proposal[0]
        page_text = citation_doc.pages[0].text if citation_doc.pages else citation_doc.full_text
        excerpt = _pick_citation_excerpt(page_text)
        periodicity = (
            "annual"
            if re.search(r"annual|year", proposal[0].full_text, re.I)
            else "monthly"
        )
        structured = ContractAnalysisStructured(
            verdict=base_verdict,  # type: ignore[arg-type]
            currency="EUR",
            periodicity=periodicity,  # type: ignore[arg-type]
            currentPrice=current_price,
            proposalPrice=proposal_price,
            permanenceMonths=permanence,
            penaltyNotes=penalty,
            coverages=_extract_coverages(proposal[0].full_text),
            risks=(
                ["Contradictory permanence clauses"]
                if contradiction
                else ["Mock analyzer — verify manually"]
            ),
            citations=(
                [AnalysisCitation(documentId=citation_doc.document_id, page=1, excerpt=excerpt)]
                if excerpt
                else []
            ),
            summary=_build_summary(
                bundle, current_price, proposal_price, base_verdict
            ),
            priceNotes=_format_price_notes(current_price, proposal_price),
            coverageNotes="Derived from extracted proposal text (mock).",
            unknownFields=["currentPrice"] if current_price is None else [],
        )
        structured.verdict = verdict_from_prices(structured)
        return self._wrap(structured, _estimate_tokens(bundle))

    def _wrap(
        self, structured: ContractAnalysisStructured, input_tokens: int
    ) -> ContractAnalyzerResult:
        return ContractAnalyzerResult(
            structured=structured,
            meta=AnalyzerRunMeta(
                provider="mock",
                model=MODEL,
                prompt_version=PROMPT_VERSION,
                schema_version=SCHEMA_VERSION,
                input_tokens=input_tokens,
                output_tokens=256,
                retries=0,
            ),
        )


def _extract_price(text: str) -> float | None:
    match = re.search(r"(?:price|tariff|€|eur)\s*[:\s]*([0-9]+(?:[.,][0-9]+)?)", text, re.I)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _extract_permanence(text: str) -> int | None:
    match = re.search(r"permanence[:\s]*([0-9]+)\s*months?", text, re.I)
    return int(match.group(1)) if match else None


def _extract_line(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.I)
    return match.group(1).strip() if match else None


def _extract_coverages(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^coverage:", stripped, re.I):
            out.append(re.sub(r"^coverage:\s*", "", stripped, flags=re.I))
    return out


def _pick_citation_excerpt(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 12:
            return stripped[:120]
    return None


def _build_summary(
    bundle: RedactedExtractedBundle,
    current_price: float | None,
    proposal_price: float | None,
    verdict: str,
) -> str:
    current_label = "unknown" if current_price is None else str(current_price)
    proposal_label = "unknown" if proposal_price is None else str(proposal_price)
    return (
        f'Mock comparison for "{bundle.title}" ({bundle.service_type}) — '
        f"verdict {verdict}. Current={current_label} vs proposal={proposal_label}."
    )


def _format_price_notes(current: float | None, proposal: float | None) -> str:
    if current is None or proposal is None:
        return "Could not extract comparable prices from all documents."
    return f"Normalized comparison delta (same periodicity): {(proposal - current):.2f}"


def _estimate_tokens(bundle: RedactedExtractedBundle) -> int:
    chars = sum(len(doc.full_text) for doc in bundle.documents)
    return max(1, (chars + 3) // 4)
