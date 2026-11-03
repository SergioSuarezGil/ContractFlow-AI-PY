from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PROMPT_VERSION = "contract-compare-v1"
SCHEMA_VERSION = "structured-v1"

Verdict = Literal["better", "worse", "depends", "abstain"]
Periodicity = Literal["monthly", "annual", "other", "unknown"]


class AnalysisCitation(BaseModel):
    documentId: str
    page: int | None = None
    excerpt: str = Field(max_length=500)


class ContractAnalysisStructured(BaseModel):
    verdict: Verdict
    currency: str | None = None
    periodicity: Periodicity = "unknown"
    currentPrice: float | None = Field(default=None, ge=0)
    proposalPrice: float | None = Field(default=None, ge=0)
    permanenceMonths: int | None = Field(default=None, ge=0)
    penaltyNotes: str | None = None
    coverages: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    citations: list[AnalysisCitation] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    priceNotes: str = ""
    coverageNotes: str = ""
    unknownFields: list[str] = Field(default_factory=list)
