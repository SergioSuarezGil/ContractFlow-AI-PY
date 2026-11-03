# Infrastructure (local)

Local infra is MongoDB, RabbitMQ, LocalStack S3, and Keycloak. `./scripts/infra_up.sh` starts that stack (override the checkout with `CONTRACTFLOW_TS_ROOT` if it is not beside this repo).

## Host ports

| Service | Host port |
| --- | --- |
| contracts-api | **3010** |
| ai-worker | **3011** |
| pdf-worker | **3012** |
| ai-worker-stub / pdf-worker-stub | **3111 / 3112** (`--profile stubs`) |

Shared infra uses 27017, 5672, 4566, and 8080.

Compose sets `CONTRACTS_REPO=mongo`, `OBJECT_STORAGE=s3`, and `DOCUMENT_SOURCE=mongo`, so ai-worker loads document bytes from Mongo + LocalStack. `GET /internal/v1/documents/{id}` remains available for `DOCUMENT_SOURCE=http`. pdf-worker uploads the PDF to S3 and still `PUT`s `/internal/v1/reports/{id}` so the API can serve the download (`INTERNAL_API_TOKEN`).

`/metrics` is on 3010, 3011, and 3012.

## Files

| File | Role |
| --- | --- |
| `../scripts/infra_up.sh` | Starts TS `infra/compose.yaml` (project `contractflow`) |
| `../scripts/infra_down.sh` | Stops that infra stack |
| `compose.python.yaml` | PY apps on external network `contractflow_default` |
| `docker/Dockerfile.*` | Images for contracts-api, ai-worker, pdf-worker |

## Commands

From repo root (`ContractFlow-AI-PY`):

```bash
cp -n .env.example .env   # once

# 1) Shared infra (see CONTRACTFLOW_TS_ROOT below)
./scripts/infra_up.sh

# 2) Python apps on :3010/:3011/:3012
docker compose -f infra/compose.python.yaml up -d --build

curl -sS http://127.0.0.1:3010/health
curl -sS http://127.0.0.1:3011/health
curl -sS http://127.0.0.1:3012/health

# End-to-end smoke (create → compare → COMPLETED → download PDF)
./scripts/smoke_docker.sh

# Optional lightweight stubs (ports 3111/3112 — do not clash with real workers)
docker compose -f infra/compose.python.yaml --profile stubs up -d

docker compose -f infra/compose.python.yaml down
./scripts/infra_down.sh
```

Override the infra checkout if needed:

```bash
CONTRACTFLOW_TS_ROOT=/path/to/shared-infra-checkout ./scripts/infra_up.sh
```
