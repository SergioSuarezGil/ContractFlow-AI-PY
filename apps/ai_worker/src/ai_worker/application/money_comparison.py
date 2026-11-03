from __future__ import annotations

from ai_worker.application.contract_analysis_schema import (
    ContractAnalysisStructured,
    Periodicity,
    Verdict,
)

_MONTHLY_FACTOR: dict[Periodicity, float] = {
    "monthly": 1.0,
    "annual": 1.0 / 12.0,
    "other": 1.0,
    "unknown": 1.0,
}


def normalize_monthly_price(price: float | None, periodicity: Periodicity) -> float | None:
    if price is None:
        return None
    return price * _MONTHLY_FACTOR.get(periodicity, 1.0)


def verdict_from_prices(structured: ContractAnalysisStructured) -> Verdict:
    current = normalize_monthly_price(structured.currentPrice, structured.periodicity)
    proposal = normalize_monthly_price(structured.proposalPrice, structured.periodicity)
    if current is None or proposal is None:
        return structured.verdict
    delta = proposal - current
    tolerance = max(0.5, current * 0.01)
    if abs(delta) <= tolerance:
        return "depends"
    return "better" if delta < 0 else "worse"
