#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS_ROOT="${CONTRACTFLOW_TS_ROOT:-$ROOT/../ContractFlow-AI-TS}"
TS_INFRA="$TS_ROOT/infra"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$TS_INFRA/compose.yaml" ]]; then
  echo "Missing TS infra at: $TS_INFRA/compose.yaml" >&2
  exit 1
fi

echo "Stopping shared infra from $TS_INFRA"
docker compose \
  -f "$TS_INFRA/compose.yaml" \
  --project-directory "$TS_INFRA" \
  --env-file "$ENV_FILE" \
  down

echo "Infra down."
