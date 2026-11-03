#!/usr/bin/env bash
# Open the React demo against this API.
# Entry URL (Keycloak): http://localhost:8088
# API (direct):         http://127.0.0.1:3010
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/infra_up.sh

docker compose -f infra/compose.python.yaml up -d --build \
  contracts-api ai-worker pdf-worker web-demo

echo
echo "Web:  http://localhost:8088"
echo "API:  http://127.0.0.1:3010/health"
echo "Sign in as demo / demo. Do not use the Vite server on :5173 for login."
