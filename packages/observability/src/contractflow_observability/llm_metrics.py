from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram

DEFAULT_LLM_TARIFFS: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.0, 0.0),
    "mock": (0.0, 0.0),
}


def estimate_llm_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    tariffs: dict[str, tuple[float, float]] | None = None,
) -> float:
    table = tariffs or DEFAULT_LLM_TARIFFS
    input_rate, output_rate = table.get(model, table["mock"])
    return (input_tokens / 1000) * input_rate + (output_tokens / 1000) * output_rate


class LlmMetrics:
    """Counters recorded when the ai-worker runs an analysis."""

    def __init__(self, registry: CollectorRegistry) -> None:
        labels = ["provider", "model"]
        self.requests_total = Counter(
            "contractflow_llm_requests_total",
            "LLM analysis requests",
            ["provider", "model", "outcome"],
            registry=registry,
        )
        self.duration_seconds = Histogram(
            "contractflow_llm_duration_seconds",
            "LLM request duration",
            labels,
            buckets=(0.25, 0.5, 1, 2, 5, 10, 20, 40, 60),
            registry=registry,
        )
        self.input_tokens_total = Counter(
            "contractflow_llm_input_tokens_total",
            "LLM input tokens (estimated when the provider omits usage)",
            labels,
            registry=registry,
        )
        self.output_tokens_total = Counter(
            "contractflow_llm_output_tokens_total",
            "LLM output tokens",
            labels,
            registry=registry,
        )
        self.estimated_cost_usd_total = Counter(
            "contractflow_llm_estimated_cost_usd_total",
            "Estimated LLM spend using a versioned tariff table",
            labels,
            registry=registry,
        )
        self.retries_total = Counter(
            "contractflow_llm_retries_total",
            "LLM repair/retry attempts",
            labels,
            registry=registry,
        )

    def record(
        self,
        *,
        provider: str,
        model: str,
        outcome: str,
        duration_s: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        retries: int = 0,
    ) -> None:
        provider = provider or "mock"
        model = model or "mock"
        self.requests_total.labels(provider=provider, model=model, outcome=outcome).inc()
        self.duration_seconds.labels(provider=provider, model=model).observe(duration_s)
        if outcome != "success":
            return
        self.input_tokens_total.labels(provider=provider, model=model).inc(input_tokens)
        self.output_tokens_total.labels(provider=provider, model=model).inc(output_tokens)
        self.estimated_cost_usd_total.labels(provider=provider, model=model).inc(
            estimate_llm_cost_usd(model, input_tokens, output_tokens)
        )
        if retries:
            self.retries_total.labels(provider=provider, model=model).inc(retries)
