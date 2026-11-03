#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS_ROOT="${CONTRACTFLOW_TS_ROOT:-$ROOT/../ContractFlow-AI-TS}"
TS_INFRA="$TS_ROOT/infra"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$TS_INFRA/compose.yaml" ]]; then
  echo "Missing TS infra at: $TS_INFRA/compose.yaml" >&2
  echo "Set CONTRACTFLOW_TS_ROOT to your ContractFlow-AI-TS checkout." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy .env.example first." >&2
  exit 1
fi

echo "Starting shared infra from $TS_INFRA"
docker compose \
  -f "$TS_INFRA/compose.yaml" \
  --project-directory "$TS_INFRA" \
  --env-file "$ENV_FILE" \
  up -d

echo "Infra up. Network: contractflow_default"
