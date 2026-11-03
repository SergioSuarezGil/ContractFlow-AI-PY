from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from contractflow_contracts.paths import events_dir
from contractflow_contracts.types import KNOWN_EVENT_TYPES, KnownEventType

PAYLOAD_SCHEMA_FILES: dict[KnownEventType, str] = {
    "comparison.requested.v1": "comparison.requested.v1.schema.json",
    "comparison.completed.v1": "comparison.completed.v1.schema.json",
    "comparison.failed.v1": "comparison.failed.v1.schema.json",
    "report.requested.v1": "report.requested.v1.schema.json",
    "report.completed.v1": "report.completed.v1.schema.json",
    "report.failed.v1": "report.failed.v1.schema.json",
}


def _load_json(path_name: str) -> dict[str, Any]:
    path = events_dir() / path_name
    return json.loads(path.read_text(encoding="utf-8"))


def _resource_from_schema(schema: dict[str, Any]) -> Resource[Any]:
    return Resource.from_contents(schema, default_specification=DRAFT202012)


@lru_cache
def build_registry() -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    for file_name in (
        "envelope.schema.json",
        "comparison-result.schema.json",
        *PAYLOAD_SCHEMA_FILES.values(),
    ):
        schema = _load_json(file_name)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise SchemaError(f"Schema {file_name} missing $id")
        resources.append((schema_id, _resource_from_schema(schema)))
    registry: Registry = Registry()
    for uri, resource in resources:
        registry = registry.with_resource(uri, resource)
    return registry


@lru_cache
def envelope_validator() -> Draft202012Validator:
    schema = _load_json("envelope.schema.json")
    # Payload shape is validated per event type.
    schema = {
        **schema,
        "properties": {
            **schema["properties"],
            "payload": {"type": "object"},
        },
    }
    return Draft202012Validator(schema, registry=build_registry())


@lru_cache
def payload_validators() -> dict[KnownEventType, Draft202012Validator]:
    registry = build_registry()
    validators: dict[KnownEventType, Draft202012Validator] = {}
    for event_type, file_name in PAYLOAD_SCHEMA_FILES.items():
        schema = _load_json(file_name)
        validators[event_type] = Draft202012Validator(schema, registry=registry)
    return validators


def is_known_event_type(value: str) -> bool:
    return value in KNOWN_EVENT_TYPES
