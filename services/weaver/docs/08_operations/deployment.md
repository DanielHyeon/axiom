# 배포 절차

<!-- affects: operations -->
<!-- requires-update: 07_security/connection-security.md -->

## 이 문서가 답하는 질문

- Weaver를 어떻게 배포하는가?
- MindsDB 설정은 어떻게 하는가?
- 환경 변수는 무엇이 필요한가?
- 로컬 개발 환경은 어떻게 구성하는가?
- 프로덕션 배포 체크리스트는?

> 포트/엔드포인트 기준: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

---

## 1. 로컬 개발 환경

### 1.1 Docker Compose

```yaml
# services/weaver/docker-compose.dev.yml
version: "3.8"

services:
  weaver:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8001:8000"
    environment:
      - APP_ENV=development
      - MINDSDB_URL=http://mindsdb:47334
      - WEAVER_EXTERNAL_MODE=true
      - WEAVER_METADATA_EXTERNAL_MODE=true
      - WEAVER_METADATA_PG_MODE=true
      - WEAVER_REQUEST_GUARD_REDIS_MODE=true
      - REDIS_URL=redis://redis:6379/0
      - POSTGRES_DSN=postgresql://sample_user:sample_password@sample_pg:5432/sample_enterprise
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=weaver_dev_password
      - ENCRYPTION_KEY=dev_encryption_key_32chars
      - WEAVER_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
      - LOG_LEVEL=DEBUG
    depends_on:
      mindsdb:
        condition: service_started
      neo4j:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./app:/app/app  # Hot reload
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  mindsdb:
    image: mindsdb/mindsdb:latest
    ports:
      - "47334:47334"
    volumes:
      - mindsdb_data:/root/mindsdb_storage

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # HTTP Browser
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/weaver_dev_password
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "weaver_dev_password", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Optional: sample PostgreSQL for testing
  sample_pg:
    image: postgres:15
    ports:
      - "5433:5432"
    environment:
      - POSTGRES_DB=sample_enterprise
      - POSTGRES_USER=sample_user
      - POSTGRES_PASSWORD=sample_password
    volumes:
      - ./tests/fixtures/sample_schema.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  mindsdb_data:
  neo4j_data:
```

### 1.2 시작 절차

```bash
# 1. 인프라 서비스 시작
docker compose -f docker-compose.dev.yml up -d mindsdb neo4j sample_pg

# 2. Neo4j 인덱스 생성 (최초 1회)
docker exec -it weaver-neo4j-1 cypher-shell -u neo4j -p weaver_dev_password \
  "CREATE CONSTRAINT ds_name_unique IF NOT EXISTS FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE;
   CREATE INDEX schema_name_idx IF NOT EXISTS FOR (s:Schema) ON (s.name);
   CREATE INDEX table_name_idx IF NOT EXISTS FOR (t:Table) ON (t.name);
   CREATE INDEX column_name_idx IF NOT EXISTS FOR (c:Column) ON (c.name);"

# 3. MindsDB 시작 확인 (약 30-60초 소요)
until curl -s http://localhost:47334/api/status > /dev/null 2>&1; do
  echo "Waiting for MindsDB..."
  sleep 5
done
echo "MindsDB is ready"

# 4. Weaver 서비스 시작
docker compose -f docker-compose.dev.yml up -d weaver

# 5. 헬스체크
curl http://localhost:8001/api/query/status
```

---

## 2. Dockerfile

```dockerfile
# services/weaver/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# System dependencies for oracledb, asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

# Application code
COPY app/ app/

# Non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

## 3. 환경 변수

### 3.1 필수 환경 변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `NEO4J_PASSWORD` | Neo4j 비밀번호 | `production_password` |
| `ENCRYPTION_KEY` | 비밀번호 암호화 키 (32자) | `your_32_character_encryption_key` |

### 3.2 선택 환경 변수 (기본값 있음)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `APP_ENV` | `development` | 환경 (`development` / `staging` / `production`) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `JWT_SECRET_KEY` | `weaver-dev-secret-change-me` | JWT 서명 키 |
| `JWT_ALGORITHM` | `HS256` | JWT 알고리즘 |
| `JWT_ISSUER` | `` | JWT issuer 검증값(선택) |
| `JWT_AUDIENCE` | `` | JWT audience 검증값(선택) |
| `MINDSDB_URL` | `http://localhost:47334` | MindsDB 서버 URL |
| `MINDSDB_TIMEOUT` | `15` | MindsDB 쿼리 타임아웃 (초) |
| `MINDSDB_USER` | `` | MindsDB HTTP Basic Auth 사용자 (설정 시 인증 사용) |
| `MINDSDB_PASSWORD` | `` | MindsDB HTTP Basic Auth 비밀번호 |
| `WEAVER_EXTERNAL_MODE` | `false` | `true`면 `/api/datasources`, `/api/query`가 MindsDB 실서버와 동기화 |
| `WEAVER_METADATA_EXTERNAL_MODE` | `false` | `true`면 `/api/v1/metadata/*`가 Neo4j 저장소를 사용 |
| `WEAVER_METADATA_PG_MODE` | `false` | `true`면 `/api/v1/metadata/*`의 스냅샷/용어사전/통계가 Postgres 저장소를 사용 |
| `WEAVER_REQUEST_GUARD_REDIS_MODE` | `false` | `true`면 Rate Limit/Idempotency 저장소로 Redis 사용 |
| `REDIS_URL` | `redis://localhost:6379/0` | Request guard용 Redis URL |
| `WEAVER_REQUEST_GUARD_IDEMPOTENCY_TTL_SECONDS` | `600` | Idempotency-Key 캐시 TTL(초) |
| `POSTGRES_DSN` | `` | Postgres 영속 저장 DSN (`WEAVER_METADATA_PG_MODE=true`일 때 필수) |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 연결 URI |
| `NEO4J_USER` | `neo4j` | Neo4j 사용자 |
| `WEAVER_CORS_ALLOWED_ORIGINS` | `https://app.axiom.kr,https://canvas.axiom.kr` | 허용된 CORS 도메인(콤마 구분, `*`는 무시) |
| `WEAVER_CORS_ALLOWED_METHODS` | `GET,POST,PUT,DELETE,OPTIONS` | 허용된 CORS 메서드(콤마 구분) |
| `WEAVER_CORS_ALLOWED_HEADERS` | `Authorization,Content-Type,X-Request-Id,Idempotency-Key` | 허용된 CORS 헤더(콤마 구분) |

### 3.3 프로덕션 전용

| 변수 | 설명 |
|------|------|
| `MINDSDB_USER` | MindsDB HTTP API 인증 사용자 |
| `MINDSDB_PASSWORD` | MindsDB HTTP API 인증 비밀번호 |
| `SENTRY_DSN` | Sentry 에러 추적 DSN |

---

## 4. MindsDB 설정

### 4.1 초기 설정

MindsDB 서버가 시작된 후 초기 설정을 확인한다.

```bash
# MindsDB 상태 확인
curl http://localhost:47334/api/status

# 기존 데이터베이스 목록
curl -X POST http://localhost:47334/api/sql/query \
  -H "Content-Type: application/json" \
  -d '{"query": "SHOW DATABASES"}'
```

### 4.2 핸들러 활성화

MindsDB에서 필요한 DB 핸들러가 설치되어 있는지 확인한다.

```sql
-- 설치된 핸들러 목록
SHOW HANDLERS;

-- 필요한 핸들러 설치 (누락된 경우)
-- PostgreSQL, MySQL은 기본 포함
-- Oracle: 별도 설치 필요
```

### 4.3 MindsDB 리소스 설정

| 항목 | 개발 | 프로덕션 | 설명 |
|------|------|---------|------|
| 메모리 | 2GB | 8GB | 크로스 DB 조인 시 메모리 사용 |
| CPU | 1 코어 | 4 코어 | 동시 쿼리 처리 |
| 디스크 | 5GB | 50GB | MindsDB 내부 저장소 |
| 커넥션 풀 | 기본 | 핸들러별 10 | 동시 DB 연결 |

---

## 5. 프로덕션 배포 체크리스트

### 5.1 보안

| 항목 | 확인 |
|------|------|
| Neo4j 비밀번호 변경 (기본값 아닌지) | |
| MindsDB 인증 활성화 | |
| CORS 도메인 제한 | |
| SSL/TLS 활성화 (Neo4j, MindsDB) | |
| 환경 변수 Vault 또는 K8s Secret 사용 | |
| `APP_ENV=production` 설정 | |

### 5.2 성능

| 항목 | 확인 |
|------|------|
| Neo4j 인덱스 생성 | |
| MindsDB 메모리 할당 | |
| Uvicorn 워커 수 설정 (CPU 코어 x 2) | |
| HTTP keepalive 활성화 | |

### 5.3 모니터링

| 항목 | 확인 |
|------|------|
| Weaver 헬스체크 엔드포인트 등록 | |
| Weaver `/metrics` 스크레이프 등록 | |
| MindsDB 상태 모니터링 | |
| Neo4j 연결 모니터링 | |
| 로그 수집 (Loki/ELK) 설정 | |
| 에러 추적 (Sentry) 설정 | |

### 5.4 백업

| 항목 | 확인 |
|------|------|
| Neo4j 메타데이터 백업 스케줄 | |
| MindsDB 설정 백업 | |

---

## 6. 외부 연동 E2E 검증

Weaver 외부 모드(MindsDB + Neo4j + Postgres)를 실제로 붙여 검증한다.

### 6.1 실행 조건

- `WEAVER_RUN_E2E=1`
- `MINDSDB_URL`, `POSTGRES_DSN`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` 설정
- MindsDB/Neo4j/Postgres 컨테이너가 기동 중이어야 한다.
- (선택) 데이터소스 연결 타깃 오버라이드: `WEAVER_E2E_DS_HOST`, `WEAVER_E2E_DS_PORT`, `WEAVER_E2E_DS_DATABASE`, `WEAVER_E2E_DS_USER`, `WEAVER_E2E_DS_PASSWORD`

### 6.2 실행 명령

```bash
cd services/weaver
WEAVER_RUN_E2E=1 \
MINDSDB_URL=http://localhost:47334 \
POSTGRES_DSN=postgresql://sample_user:sample_password@localhost:5433/sample_enterprise \
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=weaver_dev_password \
PYTHONPATH=. pytest -q tests/integration/test_external_modes_e2e.py
```

### 6.3 Exit Gate (권장)

운영/CI 게이트는 skip을 허용하지 않고 live 통과만 허용한다.

```bash
cd services/weaver
WEAVER_RUN_E2E=1 \
MINDSDB_URL=http://localhost:47334 \
POSTGRES_DSN=postgresql://sample_user:sample_password@localhost:5433/sample_enterprise \
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=weaver_dev_password \
make integration-external-exit-gate LOOPS=2
```

- 실행 스크립트: `scripts/weaver_external_exit_gate.py`
- 동작:
- 필수 env 누락 시 즉시 실패
- `tests/integration/test_external_modes_e2e.py`를 반복 실행
- 테스트가 skip되면 실패 처리

### 6.4 기대 결과

- 데이터소스 생성/삭제가 MindsDB와 동기화된다.
- `/api/query`가 MindsDB 실서버에서 실행된다.
- metadata snapshot/glossary/stats가 Postgres 영속 저장소를 통해 조회된다.
- tenant A/B 교차 접근이 차단된다(다른 tenant의 datasource/detail=404, glossary/snapshot 조회=0/404).

## 7. 헬스체크

```python
# Kubernetes liveness probe
# GET /health/live → 200 OK (서버 동작 중)

# Kubernetes readiness probe
# GET /health/ready → 활성화된 외부 의존성(MindsDB/Postgres/Neo4j) 연결 확인

@app.get("/health/live")
async def liveness():
    return {"status": "alive"}

# 설정이 꺼진 의존성은 "disabled"로 표시되고 readiness 판정에서 제외됨
# settings.external_mode -> mindsdb
# settings.metadata_pg_mode -> postgres
# settings.metadata_external_mode -> neo4j
# 하나라도 "down"이면 503 + {"status":"degraded"}
```

---

## 8. 관련 문서

| 문서 | 설명 |
|------|------|
| `07_security/connection-security.md` | 보안 설정 |
| `08_operations/migration-from-kair.md` | K-AIR 이식 가이드 |
| `03_backend/service-structure.md` | 서비스 구조 |
| Core `08_operations/performance-monitoring.md` | Weaver SLO, MindsDB/예측 지연 메트릭, Sentry 설정, 알림 규칙 |
