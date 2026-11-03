from functools import lru_cache
from pathlib import Path


@lru_cache
def schemas_root() -> Path:
    """Root of vendored schemas copied from ContractFlow-AI-TS."""
    cursor = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = cursor / "schemas"
        if (candidate / "events").is_dir() and (candidate / "openapi").is_dir():
            return candidate
        cursor = cursor.parent

    raise FileNotFoundError(
        "Could not locate contract schemas (expected schemas/events and schemas/openapi)"
    )


def events_dir() -> Path:
    return schemas_root() / "events"


def openapi_yaml_path() -> Path:
    return schemas_root() / "openapi" / "openapi.yaml"


def openapi_json_path() -> Path:
    return schemas_root() / "openapi" / "openapi.json"
