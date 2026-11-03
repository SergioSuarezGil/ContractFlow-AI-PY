from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class ComparisonResult:
    id: str
    job_id: str
    contract_id: str
    verdict: Literal["better", "worse", "depends"]
    summary: str
    price_notes: str
    coverage_notes: str
    risks: list[str]
    disclaimer: str
    created_at: str
    analysis_mode: Literal["mock", "gemini"] = "mock"
    model_version: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    structured: dict[str, Any] | None = None
    llm_usage: dict[str, Any] | None = None

    def to_event_dict(self) -> dict[str, Any]:
        """CamelCase payload matching TS / JSON schemas."""
        return {
            "id": self.id,
            "jobId": self.job_id,
            "contractId": self.contract_id,
            "verdict": self.verdict,
            "summary": self.summary,
            "priceNotes": self.price_notes,
            "coverageNotes": self.coverage_notes,
            "risks": self.risks,
            "disclaimer": self.disclaimer,
            "createdAt": self.created_at,
            "analysisMode": self.analysis_mode,
            "modelVersion": self.model_version,
            "promptVersion": self.prompt_version,
            "schemaVersion": self.schema_version,
            "citations": self.citations,
            "structured": self.structured,
            "llmUsage": self.llm_usage,
        }


def comparison_result_debug(result: ComparisonResult) -> dict[str, Any]:
    return asdict(result)
