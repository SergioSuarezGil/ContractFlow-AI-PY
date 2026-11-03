#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3010}"
OWNER="${OWNER:-demo}"
HOUSEHOLD="${HOUSEHOLD:-hh_demo}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

hdr=(-H "X-Owner-Id: ${OWNER}" -H "X-Household-Id: ${HOUSEHOLD}")

echo "== health =="
curl -sfS "$BASE/health" >/dev/null
curl -sfS "http://127.0.0.1:3011/health" >/dev/null
curl -sfS "http://127.0.0.1:3012/health" >/dev/null
echo "ok"

echo "== create contract =="
CID="$(curl -sfS "${hdr[@]}" -H "Content-Type: application/json" \
  -d '{"serviceType":"electricity","providerName":"Acme","title":"Smoke home"}' \
  "$BASE/api/v1/contracts" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
echo "contract=$CID"

echo "== upload documents =="
printf 'Price: 55 monthly' >"$TMP/current.txt"
printf 'Price: 40 monthly\ncoverage: green energy' >"$TMP/proposal.txt"
curl -sfS "${hdr[@]}" -F role=current -F "file=@${TMP}/current.txt;type=text/plain" \
  "$BASE/api/v1/contracts/$CID/documents" >/dev/null
curl -sfS "${hdr[@]}" -F role=proposal -F "file=@${TMP}/proposal.txt;type=text/plain" \
  "$BASE/api/v1/contracts/$CID/documents" >/dev/null

echo "== request comparison =="
JOB="$(curl -sfS "${hdr[@]}" -X POST "$BASE/api/v1/contracts/$CID/comparisons")"
JID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["jobId"])' "$JOB")"
echo "job=$JID"

echo "== poll job =="
STATUS=""
for _ in $(seq 1 30); do
  BODY="$(curl -sfS "${hdr[@]}" "$BASE/api/v1/jobs/$JID")"
  STATUS="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "$BODY")"
  ERR="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("errorMessage") or "")' "$BODY")"
  echo "status=$STATUS"
  if [[ "$STATUS" == "COMPLETED" || "$STATUS" == "FAILED" ]]; then
    break
  fi
  sleep 1
done

if [[ "$STATUS" != "COMPLETED" ]]; then
  echo "Smoke failed: status=$STATUS error=$ERR" >&2
  exit 1
fi

echo "== download PDF =="
curl -sfS "${hdr[@]}" -o "$TMP/report.pdf" "$BASE/api/v1/jobs/$JID/report"
python3 - <<PY
from pathlib import Path
data = Path("$TMP/report.pdf").read_bytes()
assert data.startswith(b"%PDF"), data[:20]
print(f"pdf_ok bytes={len(data)}")
PY

echo "SMOKE OK job=$JID"
