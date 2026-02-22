#!/usr/bin/env bash
# Compose 환경에서 전체 스택 기동 후 5개 서비스 유닛 테스트 실행.
# 사용: ./tools/run_compose_tests.sh [--build]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BUILD="${1:-}"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-axiom}"

log() {
  printf '[COMPOSE-TEST] %s\n' "$1"
}

wait_ready() {
  local name="$1"
  local url="$2"
  for i in $(seq 1 60); do
    if curl -sS -f "$url" >/dev/null 2>&1; then
      log "$name ready: $url"
      return 0
    fi
    sleep 2
  done
  log "timeout waiting for $name: $url"
  return 1
}

# 1) 스택 기동 (앱 5개 + canvas 제외 시 빌드/기동 시간 단축 가능)
if [[ "$BUILD" == "--build" ]]; then
  log "docker compose up -d --build (all services)"
  docker compose up -d --build
else
  log "docker compose up -d"
  docker compose up -d
fi

# 2) 헬스 대기 (호스트에서 접근 가능한 URL)
log "waiting for services..."
wait_ready "synapse" "http://127.0.0.1:8003/health/live"
wait_ready "vision"  "http://127.0.0.1:8000/health/ready"
wait_ready "core"    "http://127.0.0.1:8002/api/v1/health/ready"
wait_ready "weaver"  "http://127.0.0.1:8001/health/ready"
wait_ready "oracle"  "http://127.0.0.1:8004/health/ready"

# 3) 유닛 테스트 (각 서비스 컨테이너에서 실행, 동일 네트워크/env)
FAILED=0
run_unit() {
  local svc="$1"
  log "run unit tests: $svc"
  if ! docker compose run --rm "$svc" pytest tests/unit -q --tb=short; then
    log "FAILED: $svc unit tests"
    FAILED=1
  fi
}

run_unit "synapse-svc"
run_unit "core-svc"
run_unit "vision-svc"
run_unit "weaver-svc"
run_unit "oracle-svc"

if [[ "$FAILED" -eq 1 ]]; then
  log "one or more service unit tests failed"
  exit 1
fi
log "all compose unit tests passed"
