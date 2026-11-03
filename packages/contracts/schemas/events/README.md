# Event contracts

Exchange: `contractflow.events` (topic)

## Envelope

All events share the envelope defined in `envelope.schema.json`:

| Field | Type | Required |
| --- | --- | --- |
| `eventId` | string (UUID) | yes |
| `eventType` | string | yes |
| `schemaVersion` | integer (`1`) | yes |
| `correlationId` | string | yes |
| `causationId` | string \| null | no |
| `householdId` | string | yes |
| `occurredAt` | string (ISO-8601) | yes |
| `payload` | object | yes |

## Published event types

| Routing key | Payload schema | Publishers | Consumers |
| --- | --- | --- | --- |
| `comparison.requested.v1` | `comparison.requested.v1.schema.json` | contracts-api | ai-worker |
| `comparison.completed.v1` | `comparison.completed.v1.schema.json` | ai-worker | contracts-api (results) |
| `comparison.failed.v1` | `comparison.failed.v1.schema.json` | ai-worker | contracts-api (results) |
| `report.requested.v1` | `report.requested.v1.schema.json` | ai-worker | pdf-worker |
| `report.completed.v1` | `report.completed.v1.schema.json` | pdf-worker | contracts-api (results) |
| `report.failed.v1` | `report.failed.v1.schema.json` | pdf-worker | contracts-api (results) |

Shared nested type: `comparison-result.schema.json` (mock comparison output embedded in completed/report-requested payloads).

Planned (not yet emitted in code): `document.uploaded.v1`, `document.indexed.v1`.

## Validation

Validate the envelope and payload by `eventType` before a consumer applies the event.
