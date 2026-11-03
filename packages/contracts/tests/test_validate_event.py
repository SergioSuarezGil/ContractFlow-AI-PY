from contractflow_contracts import openapi_json_path, openapi_yaml_path, validate_event


def test_rejects_envelope_missing_required_fields() -> None:
    result = validate_event(
        {
            "eventType": "comparison.requested.v1",
            "payload": {},
        }
    )
    assert result["ok"] is False
    assert len(result["error"]) > 0


def test_rejects_payload_missing_required_fields() -> None:
    result = validate_event(
        {
            "eventId": "e1",
            "eventType": "comparison.requested.v1",
            "schemaVersion": 1,
            "correlationId": "c1",
            "causationId": None,
            "householdId": "h1",
            "occurredAt": "2026-01-01T00:00:00.000Z",
            "payload": {"jobId": "j1"},
        }
    )
    assert result["ok"] is False
    assert "required" in result["error"].lower() or "contractid" in result["error"].lower()


def test_accepts_valid_comparison_requested() -> None:
    result = validate_event(
        {
            "eventId": "e1",
            "eventType": "comparison.requested.v1",
            "schemaVersion": 1,
            "correlationId": "c1",
            "causationId": None,
            "householdId": "h1",
            "occurredAt": "2026-01-01T00:00:00.000Z",
            "payload": {
                "jobId": "j1",
                "contractId": "c1",
                "ownerId": "o1",
                "currentDocumentIds": [],
                "proposalDocumentIds": [],
                "title": "Test",
                "providerName": "Acme",
                "serviceType": "electricity",
            },
        }
    )
    assert result["ok"] is True


def test_openapi_artifacts_exist() -> None:
    assert openapi_yaml_path().is_file()
    assert openapi_json_path().is_file()


def test_accepts_comparison_completed_with_result_ref() -> None:
    result = validate_event(
        {
            "eventId": "e2",
            "eventType": "comparison.completed.v1",
            "schemaVersion": 1,
            "correlationId": "c1",
            "causationId": "e1",
            "householdId": "h1",
            "occurredAt": "2026-01-01T00:00:00.000Z",
            "payload": {
                "jobId": "j1",
                "contractId": "c1",
                "ownerId": "o1",
                "comparisonId": "cmp1",
                "verdict": "better",
                "comparison": {
                    "id": "cmp1",
                    "jobId": "j1",
                    "contractId": "c1",
                    "verdict": "better",
                    "summary": "ok",
                    "priceNotes": "",
                    "coverageNotes": "",
                    "risks": [],
                    "disclaimer": "demo",
                    "createdAt": "2026-01-01T00:00:00.000Z",
                },
            },
        }
    )
    assert result["ok"] is True
