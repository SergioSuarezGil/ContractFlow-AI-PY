from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from ai_worker.application.contract_analysis_schema import ContractAnalysisStructured
from ai_worker.application.types import RedactedExtractedBundle


@dataclass(frozen=True)
class AnalyzerRunMeta:
    provider: Literal["mock", "gemini"]
    model: str
    prompt_version: str
    schema_version: str
    input_tokens: int
    output_tokens: int
    retries: int


@dataclass(frozen=True)
class ContractAnalyzerResult:
    structured: ContractAnalysisStructured
    meta: AnalyzerRunMeta


class ContractAnalyzerPort(Protocol):
    async def analyze(self, bundle: RedactedExtractedBundle) -> ContractAnalyzerResult: ...
