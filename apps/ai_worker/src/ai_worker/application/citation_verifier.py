from __future__ import annotations

import re

from ai_worker.application.contract_analysis_schema import AnalysisCitation
from ai_worker.application.types import ExtractedDocument


def verify_citations(
    citations: list[AnalysisCitation],
    documents: list[ExtractedDocument],
) -> tuple[bool, str | None]:
    by_id = {doc.document_id: doc for doc in documents}
    for citation in citations:
        doc = by_id.get(citation.documentId)
        if doc is None:
            return False, f"Citation references unknown document {citation.documentId}"
        if citation.page is not None:
            page = next((p for p in doc.pages if p.page_number == citation.page), None)
            haystack = page.text if page else ""
        else:
            haystack = doc.full_text
        needle = citation.excerpt.strip()
        if not needle or _normalize(needle) not in _normalize(haystack):
            return False, f"Citation excerpt not found in document {citation.documentId}"
    return True, None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()
