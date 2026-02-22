#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VISION_BASE_URL="${VISION_BASE_URL:-http://localhost:8000}"
CORE_BASE_URL="${CORE_BASE_URL:-http://localhost:8002}"
CASE_ID="${CASE_ID:-case-s13-regression}"
BUILD="${1:-}"

log() {
  printf '[S13-REGRESSION] %s\n' "$1"
}

request() {
  local method="$1"
  local url="$2"
  local data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -X "$method" "$url" -H "Content-Type: application/json" -H "Authorization: mock_token_staff" -d "$data"
  else
    curl -sS -X "$method" "$url" -H "Authorization: mock_token_viewer"
  fi
}

wait_ready() {
  local name="$1"
  local url="$2"
  for _ in $(seq 1 30); do
    if curl -sS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  log "$name readiness timeout: $url"
  return 1
}

extract_metric() {
  local metric_name="$1"
  local metrics_text="$2"
  METRIC_NAME="$metric_name" METRICS_TEXT="$metrics_text" python3 - <<'PY'
import os
import re

metric = os.environ["METRIC_NAME"]
text = os.environ["METRICS_TEXT"]
match = re.search(rf"^{re.escape(metric)}\s+([0-9]+(?:\.[0-9]+)?)$", text, flags=re.MULTILINE)
if not match:
    raise SystemExit(f"metric not found: {metric}")
print(match.group(1))
PY
}

if [[ "$BUILD" == "--build" ]]; then
  log "docker compose up -d --build core-svc vision-svc"
  docker compose up -d --build core-svc vision-svc
else
  log "docker compose up -d core-svc vision-svc"
  docker compose up -d core-svc vision-svc
fi

wait_ready "vision" "${VISION_BASE_URL}/health/ready"
wait_ready "core" "${CORE_BASE_URL}/api/v1/health/ready"

log "Core readiness check"
core_ready="$(curl -sS "${CORE_BASE_URL}/api/v1/health/ready")"
CORE_READY="$core_ready" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["CORE_READY"])
if payload.get("status") != "healthy":
    raise SystemExit(f"core unhealthy: {payload}")
print("core healthy")
PY

log "Vision readiness baseline"
vision_ready_before="$(curl -sS "${VISION_BASE_URL}/health/ready")"
metrics_before="$(curl -sS "${VISION_BASE_URL}/metrics")"
calls_before="$(extract_metric "vision_root_cause_calls_total" "$metrics_before")"
errors_before="$(extract_metric "vision_root_cause_errors_total" "$metrics_before")"

log "Vision root-cause negative call (expect 404)"
http_code="$(curl -sS -o /tmp/s13_missing.json -w '%{http_code}' "${VISION_BASE_URL}/api/v3/cases/${CASE_ID}-missing/root-causes" -H "Authorization: mock_token_viewer")"
if [[ "$http_code" != "404" ]]; then
  log "unexpected status for missing case: $http_code"
  exit 1
fi

log "Vision root-cause lifecycle"
request POST "${VISION_BASE_URL}/api/v3/cases/${CASE_ID}/root-cause-analysis" '{"analysis_depth":"full","max_root_causes":3}' >/tmp/s13_run.json
request GET "${VISION_BASE_URL}/api/v3/cases/${CASE_ID}/root-cause-analysis/status" >/tmp/s13_status.json
request GET "${VISION_BASE_URL}/api/v3/cases/${CASE_ID}/root-causes" >/tmp/s13_causes.json

S13_CAUSES="$(< /tmp/s13_causes.json)" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["S13_CAUSES"])
basis = payload.get("confidence_basis") or {}
if basis.get("model") != "deterministic-risk-engine-v1":
    raise SystemExit(f"confidence_basis invalid: {basis}")
if not payload.get("root_causes"):
    raise SystemExit("root_causes is empty")
print("vision root-causes validated")
PY

log "Vision metrics delta validation"
metrics_after="$(curl -sS "${VISION_BASE_URL}/metrics")"
calls_after="$(extract_metric "vision_root_cause_calls_total" "$metrics_after")"
errors_after="$(extract_metric "vision_root_cause_errors_total" "$metrics_after")"

CALLS_BEFORE="$calls_before" CALLS_AFTER="$calls_after" ERRORS_BEFORE="$errors_before" ERRORS_AFTER="$errors_after" python3 - <<'PY'
import os

calls_delta = float(os.environ["CALLS_AFTER"]) - float(os.environ["CALLS_BEFORE"])
errors_delta = float(os.environ["ERRORS_AFTER"]) - float(os.environ["ERRORS_BEFORE"])
if calls_delta < 4:
    raise SystemExit(f"calls delta too small: {calls_delta}")
if errors_delta < 1:
    raise SystemExit(f"errors delta too small: {errors_delta}")
print(f"metrics delta ok: calls +{calls_delta}, errors +{errors_delta}")
PY

log "S13 compose regression passed"
