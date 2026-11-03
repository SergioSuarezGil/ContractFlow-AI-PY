from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from contractflow_observability.build_info import get_build_info


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line for Docker → Promtail → Loki."""

    def format(self, record: logging.LogRecord) -> str:
        build = get_build_info(record.name)
        payload: dict[str, str] = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "service": build.service,
            "gitSha": build.git_sha,
            "context": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["trace"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_json_logging(service_name: str, level: int = logging.INFO) -> None:
    import os

    os.environ["APP_SERVICE_NAME"] = service_name
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
