# 배포 절차 및 Neo4j 설정

## 이 문서가 답하는 질문

- Synapse 서비스를 어떻게 배포하는가?
- Neo4j 설정의 핵심 파라미터는?
- 개발/스테이징/프로덕션 환경 차이는?
- 헬스체크와 모니터링 설정은?

> 포트/엔드포인트 기준: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

<!-- affects: operations -->
<!-- requires-update: 03_backend/service-structure.md -->

---

## 1. 배포 아키텍처

```
┌──────────────────────────────────────────────┐
│  Docker Compose (개발) / EKS (프로덕션)       │
│                                                │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │ synapse       │  │ neo4j                 │  │
│  │ (FastAPI)     │──│ (Graph + Vector)      │  │
│  │ :8003         │  │ :7687 (bolt)          │  │
│  └──────┬───────┘  │ :7474 (http)          │  │
│         │           └──────────────────────┘  │
│         │                                      │
│  ┌──────┴───────┐  ┌──────────────────────┐  │
│  │ postgresql    │  │ redis                 │  │
│  │ (task state)  │  │ (event streams)       │  │
│  │ :5432         │  │ :6379                 │  │
│  └──────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## 2. Docker Compose (개발 환경)

```yaml
# docker-compose.yml (synapse 부분)
services:
  synapse:
    build:
      context: ./services/synapse
      dockerfile: Dockerfile
    ports:
      - "8003:8000"
    environment:
      SYNAPSE_NEO4J_URI: bolt://neo4j:7687
      SYNAPSE_NEO4J_USER: neo4j
      SYNAPSE_NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      SYNAPSE_NEO4J_DATABASE: neo4j
      SYNAPSE_DATABASE_URL: postgresql+asyncpg://axiom:${DB_PASSWORD}@postgresql:5432/axiom
      SYNAPSE_REDIS_URL: redis://redis:6379
      SYNAPSE_OPENAI_API_KEY: ${OPENAI_API_KEY}
      SYNAPSE_LLM_MODEL: gpt-4o
      SYNAPSE_EMBEDDING_MODEL: text-embedding-3-small
      SYNAPSE_HITL_CONFIDENCE_THRESHOLD: "0.75"
      SYNAPSE_LOG_LEVEL: DEBUG
    depends_on:
      neo4j:
        condition: service_healthy
      postgresql:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1g
      NEO4J_server_memory_pagecache_size: 512m
      NEO4J_dbms_security_procedures_unrestricted: apoc.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD}", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5

volumes:
  neo4j_data:
  neo4j_logs:
```

---

## 3. Dockerfile

```dockerfile
# services/synapse/Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[prod]"

# Copy application code
COPY app/ ./app/

# Non-root user
RUN adduser --disabled-password --gecos "" synapse
USER synapse

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 4. Neo4j 설정

### 4.1 환경별 메모리 설정

| 파라미터 | 개발 | 스테이징 | 프로덕션 |
|---------|------|---------|---------|
| `heap.initial_size` | 512m | 1g | 2g |
| `heap.max_size` | 1g | 2g | 4g |
| `pagecache.size` | 512m | 1g | 4g |
| 총 메모리 | 2GB | 4GB | 10GB+ |

### 4.2 벡터 인덱스 관련 설정

```properties
# Neo4j 5 vector index support is built-in
# No additional configuration needed for vector indexes
# APOC is recommended for advanced graph operations
NEO4J_PLUGINS='["apoc"]'
```

### 4.3 보안 설정

```properties
# Production security settings
NEO4J_dbms_security_auth__enabled=true
NEO4J_dbms_connector_bolt_tls__level=OPTIONAL
NEO4J_dbms_ssl_policy_bolt_enabled=true
NEO4J_dbms_ssl_policy_bolt_base__directory=/ssl
NEO4J_dbms_ssl_policy_bolt_private__key=private.key
NEO4J_dbms_ssl_policy_bolt_public__certificate=public.crt
```

### 4.4 백업 설정

```bash
# Online backup (Enterprise only) or dump (Community)
# Community Edition: stop DB → dump → restart
neo4j-admin database dump --to-path=/backup/ neo4j

# Restore
neo4j-admin database load --from-path=/backup/neo4j/ neo4j
```

---

## 5. 환경변수 목록

| 변수 | 필수 | 기본값 | 설명 |
|------|------|-------|------|
| `SYNAPSE_NEO4J_URI` | Y | - | Neo4j Bolt URI |
| `SYNAPSE_NEO4J_USER` | Y | - | Neo4j 사용자 |
| `SYNAPSE_NEO4J_PASSWORD` | Y | - | Neo4j 비밀번호 |
| `SYNAPSE_NEO4J_DATABASE` | N | neo4j | Neo4j 데이터베이스 |
| `SYNAPSE_DATABASE_URL` | Y | - | PostgreSQL URL |
| `SYNAPSE_REDIS_URL` | Y | - | Redis URL |
| `SYNAPSE_OPENAI_API_KEY` | Y | - | OpenAI API 키 |
| `SYNAPSE_LLM_MODEL` | N | gpt-4o | LLM 모델 |
| `SYNAPSE_EMBEDDING_MODEL` | N | text-embedding-3-small | 임베딩 모델 |
| `SYNAPSE_HITL_CONFIDENCE_THRESHOLD` | N | 0.75 | HITL 임계값 |
| `SYNAPSE_MAX_CONCURRENT_EXTRACTIONS` | N | 5 | 동시 추출 작업 수 |
| `SYNAPSE_LOG_LEVEL` | N | INFO | 로그 레벨 |

---

## 6. 헬스체크

```python
# app/main.py
@app.get("/health")
async def health_check():
    checks = {
        "neo4j": await check_neo4j(),
        "postgresql": await check_postgresql(),
        "redis": await check_redis(),
    }
    all_healthy = all(checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "version": settings.app_version,
        "schema_version": await get_schema_version()
    }


async def check_neo4j() -> bool:
    try:
        async with neo4j_client.session() as session:
            result = await session.run("RETURN 1")
            await result.single()
            return True
    except Exception:
        return False
```

---

## 7. 모니터링

### 7.1 주요 메트릭

| 메트릭 | 유형 | 알림 기준 |
|--------|------|----------|
| Neo4j 연결 풀 사용률 | Gauge | > 80% |
| 추출 작업 대기열 길이 | Gauge | > 20 |
| 추출 작업 평균 소요시간 | Histogram | > 5분 |
| HITL 대기 항목 수 | Gauge | > 100 |
| Neo4j 쿼리 평균 지연 | Histogram | > 500ms |
| LLM API 에러율 | Counter | > 5% |
| 벡터 검색 평균 지연 | Histogram | > 200ms |

### 7.2 로그 수집

```python
# Structured logging with structlog
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
```

---

## 8. 배포 체크리스트

### 8.1 최초 배포

- [ ] Neo4j 인스턴스 프로비저닝
- [ ] Neo4j 인증 설정
- [ ] PostgreSQL synapse 스키마 마이그레이션
- [ ] Redis Streams 생성 확인
- [ ] 환경변수 설정 완료
- [ ] Synapse 서비스 배포
- [ ] 부트스트랩 (Neo4j 스키마 초기화) 확인
- [ ] 헬스체크 통과 확인
- [ ] 벡터 인덱스 ONLINE 상태 확인

### 8.2 업데이트 배포

- [ ] 스키마 변경사항 확인 (SchemaVersion)
- [ ] 롤링 업데이트 (다운타임 없음)
- [ ] 헬스체크 통과 확인
- [ ] 벡터 인덱스 상태 확인

---

## 근거 문서

- `03_backend/service-structure.md` (서비스 구조)
- `03_backend/neo4j-bootstrap.md` (스키마 초기화)
- ADR-001: Neo4j 5 선택 근거
- Core 성능·모니터링 종합 (`services/core/docs/08_operations/performance-monitoring.md`): Synapse SLO, Neo4j 쿼리/벡터 검색 메트릭, 알림 규칙, 용량 계획
