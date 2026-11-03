from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)
from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily
from prometheus_client.registry import Collector

HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
_SKIP_EXACT = {"/metrics", "/health", "/ready"}


@dataclass
class ServiceMetrics:
    registry: CollectorRegistry
    service_name: str
    http_requests_total: Counter
    http_request_duration_seconds: Histogram


class _ResourceProcessCollector(Collector):
    """process_* metrics when /proc is unavailable (macOS dev)."""

    def collect(self):  # type: ignore[override]
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = float(usage.ru_maxrss)
        if sys.platform != "darwin":
            rss *= 1024
        yield GaugeMetricFamily(
            "process_resident_memory_bytes",
            "Resident memory size in bytes.",
            value=rss,
        )
        yield CounterMetricFamily(
            "process_cpu_seconds_total",
            "Total user and system CPU time spent in seconds.",
            value=float(usage.ru_utime + usage.ru_stime),
        )


def _register_default_collectors(registry: CollectorRegistry) -> None:
    probe = ProcessCollector(registry=None)
    if probe._btime:  # noqa: SLF001 — /proc boot time means the Linux collector works
        registry.register(probe)
    else:
        registry.register(_ResourceProcessCollector())
    PlatformCollector(registry=registry)
    GCCollector(registry=registry)


def create_service_metrics(service_name: str) -> ServiceMetrics:
    registry = CollectorRegistry()
    _register_default_collectors(registry)
    process_up = Gauge(
        "contractflow_process_up",
        "1 if the process is serving traffic",
        ["service"],
        registry=registry,
    )
    process_up.labels(service=service_name).set(1)
    http_requests_total = Counter(
        "contractflow_http_requests_total",
        "Total HTTP requests",
        ["service", "method", "route", "status_code"],
        registry=registry,
    )
    http_request_duration_seconds = Histogram(
        "contractflow_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["service", "method", "route", "status_code"],
        buckets=HTTP_BUCKETS,
        registry=registry,
    )
    return ServiceMetrics(
        registry=registry,
        service_name=service_name,
        http_requests_total=http_requests_total,
        http_request_duration_seconds=http_request_duration_seconds,
    )


def _should_skip(path: str) -> bool:
    if path in _SKIP_EXACT:
        return True
    return path.startswith("/health/")


class HttpMetricsMiddleware:
    """ASGI middleware equivalent to Nest createServiceMetrics().middleware."""

    def __init__(self, app: Any, metrics: ServiceMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        if _should_skip(path):
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "GET")
        status_code = 500
        started = time.perf_counter()

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            route_path = getattr(route, "path", None) or path
            labels = {
                "service": self.metrics.service_name,
                "method": method,
                "route": str(route_path),
                "status_code": str(status_code),
            }
            self.metrics.http_requests_total.labels(**labels).inc()
            self.metrics.http_request_duration_seconds.labels(**labels).observe(
                max(time.perf_counter() - started, 0.0)
            )
