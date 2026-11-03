from __future__ import annotations

import os

from ai_worker.application.ports import ContractAnalyzerPort
from ai_worker.infrastructure.llm.mock_analyzer import MockContractAnalyzer


def create_contract_analyzer() -> ContractAnalyzerPort:
    provider = (os.getenv("LLM_PROVIDER") or "mock").strip().lower()
    if provider == "gemini":
        from ai_worker.infrastructure.llm.gemini_analyzer import GeminiLangChainContractAnalyzer

        return GeminiLangChainContractAnalyzer()
    return MockContractAnalyzer()
