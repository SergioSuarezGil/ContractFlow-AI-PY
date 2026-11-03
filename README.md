# ContractFlow AI (Python)

AI-powered platform to manage **personal service contracts** and compare the **current offer vs alternative proposals** from uploaded PDFs. Analysis and comparative PDF reports run **asynchronously** via microservices.

Python / FastAPI services for contracts, async comparison, and PDF reports. Default LLM mode is **`mock`**; optional **LangChain + Gemini** uses `LLM_PROVIDER=gemini`. Private workspace notes live outside this repository.

## Status

Mongo/S3 persistence, report download, domain errors, readiness, Rabbit retries, metrics, MCP, and gRPC are in place. Default `LLM_PROVIDER=mock` and `AUTH_MODE=dev`. No CI, no remote deploy.

React demo: `./scripts/web_against_python.sh`, then open **http://localhost:8088** (Keycloak user `demo` / `demo`). Nginx on that origin proxies `/api` to the API on `:3010`. Sign in only on that origin. Do not sign in through Vite `:5173` (Strict Mode burns the one-time OIDC code).

## Stack (target)

- FastAPI (`contracts-api`, ai-worker, pdf-worker, mcp-server)
- MongoDB, RabbitMQ, S3-compatible storage, Keycloak
- LangChain + Gemini (`LLM_PROVIDER=mock|gemini`)
- uv workspace monorepo, ruff, pytest
- DDD / hexagonal boundaries

## Layout

```text
apps/
  contracts_api/   # FastAPI HTTP edge
  ai_worker/       # extract + PII + LangChain mock|gemini + publish
  pdf_worker/      # multipage PDF reports
  mcp_server/      # stdio MCP: compare_contracts, get_comparison_job
packages/
  shared/          # settings + S3 adapter
  contracts/       # OpenAPI + event schemas
  observability/   # JSON logs, build info, Prometheus helpers
  grpc_contractflow/  # WorkerHealth + ComparisonLookup stubs
infra/             # Compose overlays
tests/
```

## Prerequisites

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) (`brew install uv`)

## Quick start (local)

```bash
cp .env.example .env
uv sync --all-packages --group dev
uv run pytest
uv run ruff check .
uv run uvicorn contracts_api.main:app --app-dir apps/contracts_api/src --port 3010
# → http://127.0.0.1:3010/health  ·  docs at /docs
uv run uvicorn ai_worker.main:app --app-dir apps/ai_worker/src --port 3011
uv run uvicorn pdf_worker.main:app --app-dir apps/pdf_worker/src --port 3012
# Rabbit consume: MESSAGING=rabbit + AI_WORKER_CONSUME=true / PDF_WORKER_CONSUME=true

# MCP (stdio). Dev auth headers optional:
# CONTRACTFLOW_API_BASE=http://127.0.0.1:3010 \
# CONTRACTFLOW_OWNER_ID=demo CONTRACTFLOW_HOUSEHOLD_ID=hh_demo \
uv run --package contractflow-mcp-server mcp-server
```

Services listen on **3010–3012**.

## Infra + Compose

Shared Mongo/Rabbit/S3/Keycloak (see [infra/README.md](./infra/README.md)):

```bash
./scripts/infra_up.sh
docker compose -f infra/compose.python.yaml up -d --build
curl -sS http://127.0.0.1:3010/health
curl -sS http://127.0.0.1:3011/health
curl -sS http://127.0.0.1:3012/health
curl -sS http://127.0.0.1:3011/metrics | head
uv run pytest tests/test_spine_e2e.py -q   # in-process spine without Docker workers
```

Compose overrides persistence even if `.env` says `memory`:

- `CONTRACTS_REPO=mongo` and `OBJECT_STORAGE=s3` on contracts-api
- `DOCUMENT_SOURCE=mongo` on ai-worker (Mongo metadata + S3 bytes)
- `PDF_STORAGE=s3` on pdf-worker, with the internal API `PUT` kept as a fallback
- gRPC `ComparisonLookup` / `WorkerHealth` on `127.0.0.1:50052`

Metrics: `GET /metrics` on ports 3010–3012.

## Deployment note

**Local development only.** No GitHub Actions. Secrets stay in gitignored `.env`.

## License

Apache-2.0 — see [LICENSE](./LICENSE).
