from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildInfo:
    service: str
    git_sha: str
    build_time: str
    environment: str


def get_build_info(service_fallback: str = "unknown") -> BuildInfo:
    """Runtime build identity from env (set by Docker / compose)."""
    return BuildInfo(
        service=(os.getenv("APP_SERVICE_NAME") or service_fallback).strip() or service_fallback,
        git_sha=(os.getenv("APP_GIT_SHA") or "unknown").strip(),
        build_time=(os.getenv("APP_BUILD_TIME") or "unknown").strip(),
        environment=(os.getenv("ENVIRONMENT") or "development").strip(),
    )


def version_payload(service_fallback: str = "unknown") -> dict[str, str]:
    """Camel-case build identity embedded in /health and /health/ready."""
    info = get_build_info(service_fallback)
    return {
        "service": info.service,
        "gitSha": info.git_sha,
        "buildTime": info.build_time,
        "environment": info.environment,
    }
