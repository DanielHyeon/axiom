# Vision 배포 절차 및 환경 설정

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **근거**: 01_architecture/architecture-overview.md
> **포트/엔드포인트 기준**: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

---

## 이 문서가 답하는 질문

- Vision 서비스를 로컬/개발/프로덕션에 어떻게 배포하는가?
- 환경 변수 전체 목록과 필수/선택 여부는?
- DB 마이그레이션은 어떻게 실행하는가?
- 헬스체크와 모니터링은 어떻게 설정하는가?
- Airflow DAG는 어떻게 배포하는가?

---

## 1. 환경 변수

### 1.1 전체 환경 변수 목록

| 변수 | 필수 | 기본값 | 설명 |
|------|:----:|--------|------|
| `DATABASE_URL` | Y | - | PostgreSQL 연결 (`postgresql+asyncpg://...`) |
| `VISION_PORT` | N | `8400` | Vision 서비스 포트 |
| `VISION_HOST` | N | `0.0.0.0` | 바인드 호스트 |
| `VISION_WORKERS` | N | `4` | Uvicorn 워커 수 |
| `JWT_SECRET` | Y | - | JWT 검증 시크릿 (Core와 동일) |
| `JWT_ALGORITHM` | N | `HS256` | JWT 알고리즘 |
| `OPENAI_API_KEY` | Y | - | OpenAI API 키 (NL→피벗) |
| `OPENAI_MODEL` | N | `gpt-4o` | LLM 모델 |
| `REDIS_URL` | N | - | Redis 연결 (없으면 캐시 비활성화) |
| `REDIS_CACHE_TTL` | N | `3600` | 캐시 TTL (초) |
| `QUERY_TIMEOUT` | N | `30` | SQL 쿼리 타임아웃 (초) |
| `MAX_ROWS` | N | `1000` | 단일 쿼리 최대 반환 행 |
| `SCENARIO_SOLVER_TIMEOUT` | N | `60` | 솔버 타임아웃 (초) |
| `CAUSAL_MIN_CONFIDENCE` | N | `0.70` | 인과 연결 최소 신뢰도 |
| `ETL_SYNC_INTERVAL` | N | `3600` | ETL 자동 동기화 주기 (초) |
| `LOG_LEVEL` | N | `INFO` | 로그 수준 |
| `LOG_FORMAT` | N | `json` | 로그 형식 (`json` 또는 `console`) |
| `CORS_ORIGINS` | N | `*` | CORS 허용 오리진 |
| `DB_POOL_SIZE` | N | `10` | DB 커넥션 풀 크기 |
| `DB_MAX_OVERFLOW` | N | `10` | 최대 추가 연결 수 |
| `AIRFLOW_BASE_URL` | N | - | Airflow REST API URL (없으면 DAG 트리거 비활성화) |

### 1.2 환경별 설정 예시

#### 로컬 개발

```env
# .env.local
DATABASE_URL=postgresql+asyncpg://axiom:password@localhost:5432/axiom_dev
VISION_PORT=8400
JWT_SECRET=dev-secret-key-do-not-use-in-prod
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
REDIS_URL=redis://localhost:6379/2
LOG_LEVEL=DEBUG
LOG_FORMAT=console
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

#### 프로덕션

```env
# .env.production
DATABASE_URL=postgresql+asyncpg://axiom:${DB_PASSWORD}@${DB_HOST}:5432/axiom
VISION_PORT=8400
VISION_WORKERS=8
JWT_SECRET=${JWT_SECRET_FROM_VAULT}
OPENAI_API_KEY=${OPENAI_KEY_FROM_VAULT}
OPENAI_MODEL=gpt-4o
REDIS_URL=redis://${REDIS_HOST}:6379/2
REDIS_CACHE_TTL=3600
QUERY_TIMEOUT=30
MAX_ROWS=5000
SCENARIO_SOLVER_TIMEOUT=120
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=https://app.axiom.kr
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=20
AIRFLOW_BASE_URL=http://airflow-webserver:8080/api/v1
```

---

## 2. 로컬 개발 환경 구성

### 2.1 사전 요구사항

- Python 3.11+
- PostgreSQL 15+
- Redis 7+ (선택)
- uv (패키지 관리자)

### 2.2 설정 및 실행

```bash
# 1. 의존성 설치
cd services/vision
uv sync

# 2. 환경 변수 설정
cp .env.example .env.local
# .env.local 편집

# 3. DB 마이그레이션 (Alembic)
alembic upgrade head

# 4. Materialized View 초기 생성
python -m app.scripts.create_materialized_views

# 5. 서비스 시작
uvicorn app.main:app --host 0.0.0.0 --port 8400 --reload

# 6. API 문서 확인
# http://localhost:8400/docs (Swagger UI)
# http://localhost:8400/redoc (ReDoc)
```

---

## 3. Docker 배포

### 3.1 Dockerfile

```dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Copy application
COPY app/ app/
COPY cubes/ cubes/
COPY alembic/ alembic/
COPY alembic.ini .

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8400/health').raise_for_status()"

# Run
EXPOSE 8400
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8400", "--workers", "4"]
```

### 3.2 Docker Compose (통합)

```yaml
# docker-compose.yml 중 Vision 부분
axiom-vision:
  build:
    context: ./services/vision
    dockerfile: Dockerfile
  container_name: axiom-vision
  ports:
    - "8400:8400"
  environment:
    - DATABASE_URL=postgresql+asyncpg://axiom:${DB_PASSWORD}@postgres:5432/axiom
    - JWT_SECRET=${JWT_SECRET}
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - REDIS_URL=redis://redis:6379/2
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8400/health').raise_for_status()"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 15s
  restart: unless-stopped
```

---

## 4. DB 마이그레이션

### 4.1 Alembic 설정

```python
# alembic/env.py (핵심 설정)
from app.core.config import settings

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```

### 4.2 마이그레이션 명령

```bash
# 새 마이그레이션 생성
alembic revision --autogenerate -m "add_what_if_scenarios_table"

# 마이그레이션 적용
alembic upgrade head

# 마이그레이션 롤백
alembic downgrade -1

# 현재 버전 확인
alembic current
```

### 4.3 Materialized View 초기화

MV는 Alembic 마이그레이션과 별도로 관리한다 (DDL이 복잡하고 데이터 의존적).

```bash
# MV 생성 스크립트
python -m app.scripts.create_materialized_views

# MV 초기 데이터 로드 (OLTP → MV)
python -m app.scripts.initial_mv_refresh
```

---

## 5. 헬스체크 및 모니터링

### 5.1 헬스체크 엔드포인트

```python
@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {}

    # DB connectivity
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Redis connectivity
    if settings.REDIS_URL:
        try:
            redis = await get_redis()
            await redis.ping()
            checks["redis"] = "healthy"
        except Exception:
            checks["redis"] = "unhealthy"

    # Overall status
    is_healthy = all(v == "healthy" for v in checks.values())
    status_code = 200 if is_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "checks": checks,
            "version": settings.APP_VERSION,
            "uptime_seconds": get_uptime(),
        }
    )
```

### 5.2 메트릭 (Prometheus 호환)

```python
# Key metrics to expose
# vision_scenario_compute_duration_seconds (histogram)
# vision_pivot_query_duration_seconds (histogram)
# vision_etl_sync_duration_seconds (histogram)
# vision_llm_call_duration_seconds (histogram)
# vision_active_computations (gauge)
# vision_cache_hit_ratio (gauge)
```

### 5.3 로깅 출력 예시 (JSON)

```json
{
  "timestamp": "2026-02-19T10:30:00.000Z",
  "level": "INFO",
  "logger": "vision.engines.scenario_solver",
  "event": "scenario_compute_completed",
  "case_id": "uuid",
  "scenario_id": "uuid",
  "solver_method": "SLSQP",
  "iterations": 247,
  "duration_ms": 12500,
  "is_feasible": true,
  "feasibility_score": 0.85
}
```

---

## 6. Airflow DAG 배포

### 6.1 DAG 파일 위치

```
# Airflow DAGs 디렉토리에 심볼릭 링크 또는 복사
services/vision/airflow_dags/
└── vision_olap_full_sync.py   # Full Sync DAG

# Airflow에서 인식하도록:
cp services/vision/airflow_dags/*.py ${AIRFLOW_HOME}/dags/
```

### 6.2 Airflow 연결 설정

```bash
# Airflow CLI로 PostgreSQL 연결 등록
airflow connections add 'axiom_postgres' \
    --conn-type 'postgres' \
    --conn-host '${DB_HOST}' \
    --conn-port '5432' \
    --conn-login 'axiom' \
    --conn-password '${DB_PASSWORD}' \
    --conn-schema 'axiom'
```

---

## 7. 배포 체크리스트

### 7.1 첫 배포 시

- [ ] PostgreSQL 15+ 확인
- [ ] 환경 변수 설정 (필수 항목 모두)
- [ ] Alembic 마이그레이션 실행
- [ ] Materialized View 초기 생성
- [ ] 초기 MV REFRESH 실행
- [ ] 큐브 XML 파일 배포 (cubes/)
- [ ] 큐브 정의 업로드 (API 또는 스크립트)
- [ ] 헬스체크 확인 (GET /health)
- [ ] API 문서 접근 확인 (GET /docs)

### 7.2 업데이트 배포 시

- [ ] Docker 이미지 빌드
- [ ] Alembic 마이그레이션 (변경 사항 있을 때만)
- [ ] Rolling update (무중단)
- [ ] 헬스체크 통과 확인
- [ ] 큐브 정의 변경 시 MV 갱신

---

## 백업 및 복구

| 대상 | 백업 방법 | 주기 | 복구 시간 목표 |
|------|----------|------|:----------:|
| Vision 테이블 | pg_dump (논리적) | 일 1회 | < 1시간 |
| Materialized View | 백업 불필요 (REFRESH로 재생성) | - | REFRESH 소요 시간 |
| 큐브 XML 파일 | Git (소스 관리) | 커밋 시 | 즉시 |
| Airflow DAG | Git (소스 관리) | 커밋 시 | 즉시 |

---

## 관련 문서

- Core 성능·모니터링 종합 (`services/core/docs/08_operations/performance-monitoring.md`): Vision SLO 기준, Prometheus 메트릭, MV 갱신 모니터링, 알림 규칙

<!-- affects: 01_architecture/architecture-overview.md -->
