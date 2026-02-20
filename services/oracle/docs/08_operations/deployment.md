# 배포 절차 및 환경 설정

## 이 문서가 답하는 질문

- Oracle 서비스를 어떻게 배포하는가?
- 필수 환경 변수는 무엇인가?
- 외부 서비스 연결은 어떻게 설정하는가?
- 헬스 체크와 모니터링은 어떻게 구성하는가?

> 포트/엔드포인트 기준: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

<!-- affects: 03_backend -->

---

## 1. 사전 요구사항

| 항목 | 최소 버전 | 용도 |
|------|---------|------|
| Python | 3.11+ | 런타임 |
| Synapse | FastAPI | 메타데이터/그래프 API |
| PostgreSQL | 15+ | Target DB + 이력 저장 |
| Redis | 7.x | 캐시 (선택) |
| Docker | 24+ | 컨테이너 빌드 |
| Kubernetes | 1.28+ | 프로덕션 배포 |

---

## 2. 환경 변수

### 2.1 필수 환경 변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `ORACLE_SYNAPSE_BASE_URL` | Synapse API base URL | `http://synapse:8000/api/v1` |
| `ORACLE_SYNAPSE_SERVICE_TOKEN` | Synapse 호출용 서비스 토큰 | `oracle-service-token` |
| `ORACLE_TARGET_DB_URL` | Target DB 접속 URL | `postgresql://oracle_reader:pw@db:5432/business_db` |
| `ORACLE_LLM_API_KEY` | OpenAI API 키 | `sk-...` |

### 2.2 선택 환경 변수 (기본값 있음)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ORACLE_LLM_PROVIDER` | `openai` | LLM 프로바이더 |
| `ORACLE_LLM_MODEL` | `gpt-4o` | LLM 모델 |
| `ORACLE_LLM_BASE_URL` | - | 호환 API base URL |
| `ORACLE_EMBEDDING_PROVIDER` | `openai` | 임베딩 프로바이더 |
| `ORACLE_EMBEDDING_MODEL` | `text-embedding-3-small` | 임베딩 모델 |
| `ORACLE_SQL_TIMEOUT` | `30` | SQL 타임아웃 (초) |
| `ORACLE_MAX_ROWS` | `10000` | 최대 결과 행 수 |
| `ORACLE_ROW_LIMIT` | `1000` | API 응답 행 제한 |
| `ORACLE_MAX_JOIN_DEPTH` | `5` | SQL JOIN 최대 깊이 |
| `ORACLE_MAX_SUBQUERY_DEPTH` | `3` | 서브쿼리 최대 깊이 |
| `ORACLE_VECTOR_TOP_K` | `10` | 벡터 검색 top_k |
| `ORACLE_MAX_FK_HOPS` | `3` | FK 탐색 최대 홉 |
| `ORACLE_JUDGE_ROUNDS` | `2` | 품질 게이트 심사 횟수 |
| `ORACLE_CONF_THRESHOLD` | `0.90` | 캐시 신뢰도 임계값 |
| `ORACLE_REDIS_URL` | - | Redis URL (선택) |
| `ORACLE_LOG_LEVEL` | `INFO` | 로그 레벨 |
| `ORACLE_HOST` | `0.0.0.0` | 바인드 호스트 |
| `ORACLE_PORT` | `8000` | 서비스 포트 |
| `ORACLE_WORKERS` | `4` | uvicorn 워커 수 |

---

## 3. Docker 빌드

### 3.1 Dockerfile

```dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

# 시스템 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[prod]"

# 소스 복사
COPY app/ app/

# 비루트 사용자
RUN useradd -m oracle && chown -R oracle:oracle /app
USER oracle

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 실행
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info"]

EXPOSE 8000
```

### 3.2 빌드 및 실행

```bash
# 빌드
docker build -t axiom/oracle:latest .

# 실행
docker run -d \
    --name oracle \
    -p 8002:8000 \
    -e ORACLE_SYNAPSE_BASE_URL=http://synapse:8000/api/v1 \
    -e ORACLE_SYNAPSE_SERVICE_TOKEN=oracle-service-token \
    -e ORACLE_TARGET_DB_URL=postgresql://oracle_reader:pw@db:5432/business_db \
    -e ORACLE_LLM_API_KEY=sk-xxx \
    axiom/oracle:latest
```

---

## 4. Kubernetes 배포

### 4.1 Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oracle
  namespace: axiom
  labels:
    app: oracle
    service: oracle
spec:
  replicas: 2
  selector:
    matchLabels:
      app: oracle
  template:
    metadata:
      labels:
        app: oracle
    spec:
      containers:
      - name: oracle
        image: axiom/oracle:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: oracle-secrets
        - configMapRef:
            name: oracle-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
```

### 4.2 Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: oracle-secrets
  namespace: axiom
type: Opaque
stringData:
  ORACLE_SYNAPSE_SERVICE_TOKEN: "oracle-service-token"
  ORACLE_TARGET_DB_URL: "postgresql://oracle_reader:pw@db:5432/business_db"
  ORACLE_LLM_API_KEY: "sk-xxx"
```

### 4.3 ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: oracle-config
  namespace: axiom
data:
  ORACLE_SYNAPSE_BASE_URL: "http://synapse.axiom.svc:8000/api/v1"
  ORACLE_LLM_PROVIDER: "openai"
  ORACLE_LLM_MODEL: "gpt-4o"
  ORACLE_SQL_TIMEOUT: "30"
  ORACLE_MAX_ROWS: "10000"
  ORACLE_LOG_LEVEL: "INFO"
```

---

## 5. 헬스 체크

### 5.1 엔드포인트

| 경로 | 용도 | 검사 항목 |
|------|------|---------|
| `GET /health` | Liveness | 서비스 프로세스 생존 여부 |
| `GET /health/ready` | Readiness | Synapse API + Target DB 연결 가능 여부 |

### 5.2 응답

```json
// GET /health/ready
{
    "status": "healthy",
    "checks": {
        "synapse_api": {"status": "up", "latency_ms": 9},
        "target_db": {"status": "up", "latency_ms": 12},
        "llm": {"status": "up", "latency_ms": 230}
    },
    "version": "1.0.0",
    "uptime_seconds": 3600
}
```

---

## 6. 모니터링

### 6.1 메트릭

| 메트릭 | 유형 | 설명 |
|--------|------|------|
| `oracle_requests_total` | Counter | 총 요청 수 (엔드포인트별) |
| `oracle_request_duration_seconds` | Histogram | 요청 처리 시간 |
| `oracle_sql_execution_duration_seconds` | Histogram | SQL 실행 시간 |
| `oracle_llm_calls_total` | Counter | LLM 호출 수 (목적별) |
| `oracle_llm_tokens_total` | Counter | LLM 토큰 사용량 |
| `oracle_cache_hits_total` | Counter | 캐시 히트 수 |
| `oracle_guard_rejects_total` | Counter | SQL Guard 거부 수 |
| `oracle_synapse_api_duration_seconds` | Histogram | Synapse API 호출 시간 |
| `oracle_active_connections` | Gauge | 활성 DB 커넥션 수 |

### 6.2 알림 규칙

| 조건 | 심각도 | 설명 |
|------|--------|------|
| Error rate > 5% (5분) | Warning | 에러율 증가 |
| Error rate > 20% (5분) | Critical | 서비스 장애 의심 |
| p95 지연 > 10초 | Warning | 성능 저하 |
| Synapse API 연결 실패 | Critical | 메타데이터 서비스 불가 |
| LLM 호출 실패율 > 10% | Warning | AI 서비스 불안정 |

---

## 7. 로컬 개발 환경

### 7.1 docker-compose.yml

```yaml
version: '3.8'
services:
  oracle:
    build: .
    ports:
      - "8002:8000"
    environment:
      - ORACLE_SYNAPSE_BASE_URL=http://synapse:8000/api/v1
      - ORACLE_SYNAPSE_SERVICE_TOKEN=oracle-service-token
      - ORACLE_TARGET_DB_URL=postgresql://oracle_reader:password@postgres:5432/business_db
      - ORACLE_LLM_API_KEY=${OPENAI_API_KEY}
      - ORACLE_LOG_LEVEL=DEBUG
    depends_on:
      - synapse
      - postgres

  synapse:
    image: axiom/synapse:latest
    ports:
      - "8003:8000"

  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=business_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql

volumes:
  pg_data:
```

---

## 관련 문서

- [03_backend/service-structure.md](../03_backend/service-structure.md): 서비스 구조
- [07_security/sql-safety.md](../07_security/sql-safety.md): DB 계정 설정
- [08_operations/migration-from-kair.md](./migration-from-kair.md): K-AIR 이식 가이드
- Core 성능·모니터링 종합 (`services/core/docs/08_operations/performance-monitoring.md`): Oracle 전용 Prometheus 메트릭, 알림 규칙, SLO 기준
