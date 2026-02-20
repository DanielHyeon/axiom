# Axiom Core - 배포 절차

## 이 문서가 답하는 질문

- 개발/스테이징/프로덕션 환경은 어떻게 구성되는가?
- Docker Compose로 로컬 개발 환경을 어떻게 실행하는가?
- EKS(Kubernetes) 배포는 어떻게 수행하는가?

> 포트/엔드포인트 기준: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

<!-- affects: operations -->
<!-- requires-update: 08_operations/configuration.md -->

---

## 1. 환경 구성

### 1.1 환경별 차이

| 항목 | 개발 (local) | 스테이징 (staging) | 프로덕션 (production) |
|------|------------|------------------|---------------------|
| 인프라 | Docker Compose | EKS (1 노드) | EKS (3+ 노드) |
| DB | PostgreSQL 15 (컨테이너) | RDS PostgreSQL | RDS PostgreSQL (Multi-AZ) |
| Redis | Redis 7 (컨테이너) | ElastiCache | ElastiCache (클러스터) |
| LLM | Ollama (로컬) 또는 OpenAI | OpenAI | OpenAI + Anthropic (폴백) |
| 스토리지 | MinIO (컨테이너) | S3 | S3 |
| 로깅 | stdout | CloudWatch | CloudWatch + DataDog |
| SSL | 없음 | ALB (ACM 인증서) | ALB (ACM 인증서) |

---

## 2. Docker Compose (로컬 개발)

### 2.1 서비스 구성

```yaml
# infra/docker/docker-compose.yml

version: '3.8'

services:
  # === 인프라 ===
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: axiom
      POSTGRES_USER: axiom
      POSTGRES_PASSWORD: axiom_dev
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  minio:
    image: minio/minio
    ports: ["9000:9000", "9001:9001"]
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin

  neo4j:
    image: neo4j:5-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/neo4j_dev
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'

  # === Axiom Core ===
  core-api:
    build: ../../services/core
    ports: ["8000:8000"]
    depends_on: [postgres, redis, minio]
    environment:
      DATABASE_URL: postgresql+asyncpg://axiom:axiom_dev@postgres:5432/axiom
      REDIS_URL: redis://redis:6379
      MINIO_ENDPOINT: minio:9000
      JWT_SECRET_KEY: dev-secret-key-change-in-production
      DEFAULT_LLM_PROVIDER: openai
      DEFAULT_LLM_MODEL: gpt-4o
    volumes:
      - ../../services/core:/app  # 핫 리로드

  # === Workers ===
  core-sync-worker:
    build: ../../services/core
    command: python -m app.workers.sync
    depends_on: [postgres, redis]
    environment: *core-env  # core-api와 동일 환경

  core-watch-worker:
    build: ../../services/core
    command: python -m app.workers.watch_cep
    depends_on: [redis]
    environment: *core-env

volumes:
  postgres_data:
```

### 2.2 실행 방법

```bash
# 전체 서비스 시작
cd infra/docker
docker compose up -d

# 로그 확인
docker compose logs -f core-api

# DB 마이그레이션
docker compose exec core-api alembic upgrade head

# 개발 서버 (핫 리로드)
docker compose up core-api  # volumes 마운트로 코드 변경 자동 반영
```

---

## 3. EKS 배포

### 3.1 배포 아티팩트

```
infra/k8s/
  ├── base/                    # 공통 리소스
  │   ├── namespace.yaml
  │   ├── configmap.yaml
  │   └── secrets.yaml
  ├── core/                    # Core 서비스
  │   ├── deployment.yaml
  │   ├── service.yaml
  │   ├── hpa.yaml             # 자동 스케일링
  │   ├── pdb.yaml                   # PodDisruptionBudget (resilience-patterns.md §6.4)
  │   └── ingress.yaml
  ├── workers/                 # Worker 배포
  │   ├── sync-worker.yaml
  │   ├── watch-worker.yaml
  │   ├── ocr-worker.yaml
  │   ├── extract-worker.yaml
  │   └── generate-worker.yaml
  └── kustomization.yaml
```

### 3.2 배포 절차

```bash
# 1. 이미지 빌드 + ECR 푸시
docker build -t axiom-core:latest services/core/
docker tag axiom-core:latest 123456789.dkr.ecr.ap-northeast-2.amazonaws.com/axiom-core:v1.0.0
docker push ...

# 2. Kubernetes 배포
kubectl apply -k infra/k8s/

# 3. 마이그레이션 (Job으
kubectl apply -f infra/k8s/jobs/migration.yaml

# 4. 배포 확인
kubectl get pods -n axiom
kubectl logs -f deployment/core-api -n axiom

# 5. 롤백 (문제 발생 시)
kubectl rollout undo deployment/core-api -n axiom
```

---

## 4. K8s Probe & 헬스체크

```python
# app/api/health.py

# --- Startup Probe ---
@router.get("/health/startup")
async def startup():
    """Startup Probe - 서비스 기동 완료 확인"""
    return {"status": "started"}


# --- Liveness Probe ---
@router.get("/health/live")
async def liveness():
    """Liveness Probe - 프로세스 생존 확인"""
    return {"status": "alive"}


# --- Readiness Probe ---
@router.get("/health/ready")
async def readiness():
    """Readiness Probe - DB, Redis 연결 확인"""
    checks = {}

    # DB 연결
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Redis 연결
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"

    status = "healthy" if all(v == "healthy" for v in checks.values()) else "unhealthy"
    return {"status": status, "checks": checks}
```

> **전체 Probe 설계**: 서비스별 Probe 설정, PDB, HPA 상세는 [resilience-patterns.md](../01_architecture/resilience-patterns.md) §6을 참조한다.

---

## 근거

- K-AIR process-gpt-main (K8s 매니페스트, docker-compose)
- K-AIR 역설계 보고서 섹션 12 (인프라 및 배포)
- [08_operations/performance-monitoring.md](./performance-monitoring.md) (SLO/SLA, Prometheus 메트릭, 알림 규칙, 용량 계획)
- [08_operations/logging-system.md](./logging-system.md) (구조화 로깅, Fluent Bit 수집, 환경별 로그 설정, 보관 정책)
- [01_architecture/resilience-patterns.md](../01_architecture/resilience-patterns.md) (Circuit Breaker, Fallback, DLQ, K8s Probe, PDB)
