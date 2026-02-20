# 데이터베이스 운영 관리

<!-- affects: operations, backend, data, security -->
<!-- requires-update: 08_operations/performance-monitoring.md, 08_operations/logging-system.md -->

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **범위**: Cross-service (PostgreSQL, Neo4j, Redis)

---

## 이 문서가 답하는 질문

- 데이터베이스 백업/복구 전략은 어떻게 구성되는가?
- 정기 유지보수(VACUUM, REINDEX, 통계 갱신)는 어떻게 수행하는가?
- 슬로우 쿼리 감지 및 대응 절차는?
- DB 재해복구(DR) 계획은?
- 관리자 대시보드에서 DB 상태를 어떻게 확인하는가?
- DB 관련 로그 이벤트와 알림은 어떻게 구성되는가?

---

## 1. 데이터베이스 인프라 현황

### 1.1 데이터베이스별 역할

```
┌─ Axiom 데이터베이스 구성 ─────────────────────────────────────────┐
│                                                                     │
│  ┌─ PostgreSQL (RDS) ──────────────────────────────────────┐      │
│  │ 목적: 트랜잭션 데이터 (OLTP), Event Outbox               │      │
│  │ 버전: 15.x                                               │      │
│  │ 사용 서비스: Core, Vision (스키마 분리)                   │      │
│  │                                                           │      │
│  │ Core 스키마:                                              │      │
│  │   tenants, users, cases, proc_def, bpm_proc_inst,        │      │
│  │   bpm_work_item, watch_*, event_outbox, documents        │      │
│  │                                                           │      │
│  │ Vision 스키마:                                            │      │
│  │   what_if_scenarios, scenario_*, cube_definitions,        │      │
│  │   etl_sync_history, causal_*, Materialized Views         │      │
│  └───────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌─ Neo4j ─────────────────────────────────────────────────┐      │
│  │ 목적: 메타데이터 그래프, 온톨로지, 벡터 검색             │      │
│  │ 버전: 5.x (Community → Enterprise 전환 검토 중)          │      │
│  │ 사용 서비스: Oracle (읽기), Synapse (읽기/쓰기),         │      │
│  │             Weaver (읽기/쓰기)                            │      │
│  │                                                           │      │
│  │ 노드 유형:                                               │      │
│  │   DataSource, Schema, Table, Column (메타데이터)          │      │
│  │   Resource, Process, Measure, KPI (온톨로지)              │      │
│  │   Query, ValueMapping (NL2SQL 캐시)                      │      │
│  │   FabricSnapshot, SnapshotDiff (버전 관리)               │      │
│  └───────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌─ Redis (ElastiCache) ───────────────────────────────────┐      │
│  │ 목적: 캐시, 세션, Rate Limiting, Event Bus (Streams)     │      │
│  │ 버전: 7.x                                                │      │
│  │ 사용 서비스: 전체 (Core, Oracle, Vision, Synapse, Weaver)│      │
│  │                                                           │      │
│  │ 용도별 키 패턴:                                          │      │
│  │   cache:* (API/LLM 응답 캐시)                            │      │
│  │   session:* (사용자 세션)                                │      │
│  │   rate_limit:* (API Rate Limiting)                       │      │
│  │   axiom:events/watches/workers (Redis Streams)           │      │
│  │   event:processed:* (멱등성 키)                          │      │
│  └───────────────────────────────────────────────────────────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 현재 사양 (performance-monitoring.md §10 참조)

| 리소스 | 사양 | 비고 |
|--------|------|------|
| PostgreSQL (RDS) | 4 vCPU, 16GB RAM, 100GB gp3 | ap-northeast-2, Single-AZ |
| Neo4j | 4 vCPU, 10GB RAM, 50GB | EKS StatefulSet |
| Redis (ElastiCache) | 2 vCPU, 4GB RAM | cache.r6g.large |

---

## 2. 백업 전략

### 2.1 PostgreSQL 백업

```
┌─ PostgreSQL 백업 계층 ──────────────────────────────────────────┐
│                                                                   │
│  Layer 1: RDS 자동 백업 (Point-in-Time Recovery)                │
│  ├── 보관 기간: 7일                                              │
│  ├── 백업 윈도우: 매일 03:00-04:00 KST (서비스 영향 최소)       │
│  ├── 복구 가능 범위: 5분 단위 (WAL 기반)                        │
│  └── RPO: 5분, RTO: ~30분                                       │
│                                                                   │
│  Layer 2: RDS 수동 스냅샷 (주요 이벤트 전)                      │
│  ├── 트리거: 배포 전, 마이그레이션 전, 대량 데이터 변경 전      │
│  ├── 보관 기간: 30일 (자동 삭제)                                │
│  ├── 네이밍: axiom-{env}-{날짜}-{사유}                          │
│  └── 예시: axiom-prod-20260220-pre-migration-v42               │
│                                                                   │
│  Layer 3: 논리 백업 (pg_dump, 월 1회)                           │
│  ├── 대상: 스키마 + 메타데이터 테이블만 (대량 데이터 제외)      │
│  ├── 저장소: S3 (axiom-backups/{env}/postgres/)                 │
│  ├── 보관: 90일                                                  │
│  └── 목적: 교차 리전 복원, 특정 테이블 복구                     │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

```yaml
# infra/terraform/rds.tf

resource "aws_db_instance" "axiom_postgres" {
  identifier = "axiom-${var.env}"
  engine     = "postgres"
  engine_version = "15.4"

  # 백업 설정
  backup_retention_period = 7              # 7일 자동 백업
  backup_window           = "18:00-19:00"  # UTC (KST 03:00-04:00)
  copy_tags_to_snapshot   = true
  delete_automated_backups_on_deletion = false

  # 모니터링
  monitoring_interval     = 60             # Enhanced Monitoring 60초
  monitoring_role_arn     = aws_iam_role.rds_monitoring.arn
  performance_insights_enabled = true
  performance_insights_retention_period = 7 # 7일

  # 암호화
  storage_encrypted = true
  kms_key_id       = aws_kms_key.rds.arn
}
```

### 2.2 Neo4j 백업

```
┌─ Neo4j 백업 계층 ────────────────────────────────────────────────┐
│                                                                    │
│  Layer 1: neo4j-admin dump (일 1회)                               │
│  ├── 스케줄: 매일 04:00 KST (CronJob)                            │
│  ├── 저장소: S3 (axiom-backups/{env}/neo4j/)                     │
│  ├── 보관: 7일                                                    │
│  ├── RPO: 24시간, RTO: ~1시간                                    │
│  └── 주의: Community Edition은 온라인 백업 미지원                │
│                                                                    │
│  Layer 2: FabricSnapshot (논리적 버전 관리)                       │
│  ├── 데이터소스 인트로스펙션 시 자동 생성                        │
│  ├── SnapshotDiff로 변경 이력 추적                               │
│  └── 비즈니스 데이터 복구 가능 (스키마 메타데이터)               │
│                                                                    │
│  Layer 3: Cypher Export (월 1회)                                  │
│  ├── APOC 절차로 노드/관계 JSON 내보내기                        │
│  ├── 저장소: S3 (axiom-backups/{env}/neo4j/exports/)            │
│  └── 목적: 교차 환경 마이그레이션, 데이터 감사                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

```yaml
# infra/k8s/cronjob-neo4j-backup.yaml

apiVersion: batch/v1
kind: CronJob
metadata:
  name: neo4j-backup
spec:
  schedule: "0 19 * * *"  # UTC 19:00 = KST 04:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: neo4j-backup
              image: neo4j:5-enterprise  # dump 명령 필요
              command:
                - /bin/sh
                - -c
                - |
                  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
                  neo4j-admin database dump neo4j \
                    --to-path=/backups/
                  aws s3 cp /backups/neo4j.dump \
                    s3://axiom-backups/${ENV}/neo4j/${TIMESTAMP}.dump
                  # 7일 이전 백업 삭제
                  aws s3 ls s3://axiom-backups/${ENV}/neo4j/ \
                    | awk '{print $4}' \
                    | head -n -7 \
                    | xargs -I{} aws s3 rm s3://axiom-backups/${ENV}/neo4j/{}
          restartPolicy: OnFailure
```

### 2.3 Redis 백업

```
┌─ Redis 백업 전략 ─────────────────────────────────────────────────┐
│                                                                     │
│  [결정] Redis는 캐시/임시 데이터이므로 전통적 백업을 하지 않는다. │
│                                                                     │
│  근거:                                                              │
│  - 캐시 데이터: 재생성 가능 (원본은 PostgreSQL/Neo4j)              │
│  - 세션 데이터: 유실 시 재로그인으로 복구                          │
│  - Rate Limit 카운터: 유실 허용 (자동 초기화)                     │
│  - Redis Streams: Event Outbox에 원본 존재 (재발행 가능)          │
│  - 멱등성 키: 유실 시 이벤트 중복 처리 가능 (at-least-once)      │
│                                                                     │
│  ElastiCache 자체 보호:                                            │
│  - Multi-AZ 자동 장애조치 (프로덕션)                              │
│  - AOF (Append Only File) 활성화                                   │
│  - 자동 스냅샷: 1일 1회, 1일 보관                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4 백업 검증

```yaml
# 월 1회 백업 복원 테스트 (수동)

절차:
  1. RDS 스냅샷에서 테스트 인스턴스 생성
     aws rds restore-db-instance-from-db-snapshot \
       --db-instance-identifier axiom-restore-test \
       --db-snapshot-identifier axiom-prod-latest

  2. 데이터 무결성 검증
     - 주요 테이블 행 수 비교
     - 최근 트랜잭션 존재 확인
     - RLS 정책 동작 확인

  3. Neo4j dump 복원 테스트
     neo4j-admin database load neo4j --from-path=/backups/
     - 노드/관계 수 비교
     - 인덱스/제약조건 확인

  4. 테스트 인스턴스 삭제
  5. 결과 기록 (Confluence/GitHub Wiki)
```

---

## 3. 정기 유지보수

### 3.1 PostgreSQL 유지보수

#### 자동 유지보수 (pg_cron)

```sql
-- pg_cron 확장 활성화 (RDS 파라미터 그룹에서 설정)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ============ 데이터 정리 ============

-- Event Outbox 정리 (매일 02:00 KST)
SELECT cron.schedule('outbox-cleanup', '0 17 * * *',  -- UTC
  $$DELETE FROM event_outbox
    WHERE status = 'PUBLISHED' AND published_at < now() - interval '7 days'$$
);

-- Event Outbox 실패 건 정리 (매일 02:05)
SELECT cron.schedule('outbox-failed-cleanup', '5 17 * * *',
  $$DELETE FROM event_outbox
    WHERE status = 'FAILED' AND created_at < now() - interval '30 days'$$
);

-- Watch 알림 정리 (매일 02:10)
SELECT cron.schedule('alerts-cleanup', '10 17 * * *',
  $$DELETE FROM watch_alerts
    WHERE status = 'acknowledged' AND acknowledged_at < now() - interval '90 days'$$
);

-- LLM 호출 로그 정리 (매일 02:15)
SELECT cron.schedule('llm-log-cleanup', '15 17 * * *',
  $$DELETE FROM llm_call_logs
    WHERE created_at < now() - interval '30 days'$$
);

-- 멱등성 키 정리 (Redis에서 자동 TTL, DB 참조 테이블이 있는 경우)
-- Redis SETNX 키: event:processed:* (TTL 7일, 자동 만료)

-- ============ 통계 갱신 ============

-- 테이블 통계 갱신 (매일 03:00)
SELECT cron.schedule('analyze-tables', '0 18 * * *',
  $$ANALYZE cases; ANALYZE bpm_work_item; ANALYZE event_outbox;
    ANALYZE watch_alerts; ANALYZE what_if_scenarios;$$
);

-- ============ VACUUM ============

-- VACUUM (RDS autovacuum이 기본 처리, 수동은 대형 삭제 후에만)
-- autovacuum 파라미터 (RDS Parameter Group):
--   autovacuum_vacuum_threshold = 50
--   autovacuum_vacuum_scale_factor = 0.1
--   autovacuum_analyze_threshold = 50
--   autovacuum_analyze_scale_factor = 0.05

-- Event Outbox는 대량 삭제 빈번하므로 별도 VACUUM 스케줄
SELECT cron.schedule('vacuum-outbox', '0 19 * * *',  -- 매일 04:00 KST
  $$VACUUM (VERBOSE, ANALYZE) event_outbox$$
);
```

#### Vision Materialized View 갱신

```sql
-- MV 갱신 (Vision 서비스, 이벤트 기반 + 주기적)

-- 이벤트 기반: data_registered 이벤트 수신 시 Vision Worker가 실행
-- 주기적 보장: 매 6시간 (놓친 이벤트 대비)
SELECT cron.schedule('mv-refresh', '0 */6 * * *',
  $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_business_fact;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dim_case_type;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dim_org;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dim_time;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dim_stk_type;$$
);
```

### 3.2 Neo4j 유지보수

```
┌─ Neo4j 정기 유지보수 ─────────────────────────────────────────────┐
│                                                                     │
│  1. 인덱스 상태 확인 (주 1회)                                     │
│     SHOW INDEXES YIELD name, state, populationPercent              │
│     WHERE state <> 'ONLINE'                                        │
│     → 비정상 인덱스 감지 시 DROP/RECREATE                         │
│                                                                     │
│  2. 제약조건 확인 (주 1회)                                        │
│     SHOW CONSTRAINTS                                               │
│     → 마이그레이션 후 제약조건 무결성 확인                        │
│                                                                     │
│  3. 고아 노드 정리 (월 1회)                                       │
│     MATCH (n) WHERE NOT (n)--()                                    │
│     AND NOT n:DataSource AND NOT n:GlossaryTerm                    │
│     RETURN labels(n), count(n)                                     │
│     → 관계 없는 노드 식별 및 정리                                 │
│                                                                     │
│  4. 벡터 인덱스 리빌드 (분기 1회 또는 대량 변경 후)              │
│     DROP INDEX table_vector_index;                                 │
│     CREATE VECTOR INDEX table_vector_index                         │
│       FOR (t:Table) ON (t.vector)                                  │
│       OPTIONS {indexConfig: {                                       │
│         `vector.dimensions`: 1536,                                 │
│         `vector.similarity_function`: 'cosine'                     │
│       }};                                                          │
│                                                                     │
│  5. 트랜잭션 로그 정리                                            │
│     Neo4j 자동 관리 (db.tx_log.rotation.retention_policy)         │
│     설정값: "2 days" (기본)                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 Redis 유지보수

```
┌─ Redis 정기 유지보수 ──────────────────────────────────────────────┐
│                                                                      │
│  1. 메모리 분석 (주 1회)                                           │
│     redis-cli memory doctor                                         │
│     redis-cli info memory                                           │
│     → used_memory_peak 대비 현재 사용량 확인                       │
│                                                                      │
│  2. 키 분포 분석 (월 1회)                                          │
│     redis-cli --bigkeys                                              │
│     redis-cli --memkeys                                              │
│     → 비정상 대형 키 식별                                          │
│                                                                      │
│  3. Streams 상태 확인 (매일, 자동 알림)                            │
│     XINFO STREAM axiom:events                                       │
│     XINFO GROUPS axiom:events                                       │
│     → Consumer Group lag, pending 메시지 확인                      │
│     → performance-monitoring.md §4 알림 규칙으로 자동화            │
│                                                                      │
│  4. Eviction 정책 확인                                              │
│     CONFIG GET maxmemory-policy                                      │
│     → allkeys-lru (캐시), noeviction (Streams)                     │
│     ⚠ ElastiCache 단일 인스턴스이므로 allkeys-lru 사용             │
│     ⚠ Streams 데이터 보호를 위해 MAXLEN으로 크기 제한              │
│                                                                      │
│  5. Slow Log 확인 (주 1회)                                         │
│     SLOWLOG GET 20                                                   │
│     → 10ms 이상 명령 패턴 분석                                     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 슬로우 쿼리 관리

### 4.1 PostgreSQL 슬로우 쿼리

```
# RDS Parameter Group 설정
log_min_duration_statement = 1000        # 1초 이상 쿼리 로그
log_statement = 'none'                   # DDL/all 대신 슬로우 쿼리만
auto_explain.log_min_duration = 3000     # 3초 이상 자동 EXPLAIN
auto_explain.log_analyze = true
auto_explain.log_format = json

# pg_stat_statements 활성화
shared_preload_libraries = 'pg_stat_statements,pg_cron'
pg_stat_statements.max = 5000
pg_stat_statements.track = all
```

#### 슬로우 쿼리 모니터링 쿼리

```sql
-- TOP 10 슬로우 쿼리 (누적 시간 기준)
SELECT
    round(total_exec_time::numeric, 2) AS total_ms,
    calls,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(max_exec_time::numeric, 2) AS max_ms,
    rows,
    LEFT(query, 100) AS query_preview
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 현재 실행 중인 장시간 쿼리 (5초 이상)
SELECT
    pid,
    now() - query_start AS duration,
    state,
    LEFT(query, 100) AS query_preview,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 seconds'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- 락 대기 확인
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    now() - blocked.query_start AS wait_duration
FROM pg_stat_activity blocked
JOIN pg_locks bl ON blocked.pid = bl.pid AND NOT bl.granted
JOIN pg_locks gl ON bl.locktype = gl.locktype
    AND bl.database IS NOT DISTINCT FROM gl.database
    AND bl.relation IS NOT DISTINCT FROM gl.relation
    AND bl.page IS NOT DISTINCT FROM gl.page
    AND bl.tuple IS NOT DISTINCT FROM gl.tuple
    AND gl.granted
JOIN pg_stat_activity blocking ON gl.pid = blocking.pid
WHERE blocked.pid != blocking.pid;
```

#### 슬로우 쿼리 로그 이벤트

```python
# app/middleware/db_logging.py

from sqlalchemy import event
import structlog
import time

logger = structlog.get_logger()

SLOW_QUERY_THRESHOLD_MS = 1000  # 1초

def setup_query_logging(engine):
    """SQLAlchemy 쿼리 실행 시간 로깅"""

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.perf_counter() - conn.info["query_start_time"].pop(-1)
        duration_ms = int(total * 1000)

        if duration_ms > SLOW_QUERY_THRESHOLD_MS:
            logger.warning(
                "db_query_slow",
                duration_ms=duration_ms,
                query=statement[:500],  # 500자 제한
                params_count=len(parameters) if parameters else 0,
            )
```

### 4.2 Neo4j 슬로우 쿼리

```
# neo4j.conf 설정
db.logs.query.enabled=INFO           # 쿼리 로그 활성화
db.logs.query.threshold=1s           # 1초 이상 쿼리 로그
db.logs.query.parameter_logging=VERBOSE
db.logs.query.max_parameter_length=200
```

```python
# app/services/neo4j_logging.py

import structlog
import time

logger = structlog.get_logger()

NEO4J_SLOW_THRESHOLD_MS = 500

async def execute_cypher_with_logging(session, query: str, params: dict = None):
    """Neo4j Cypher 실행 + 슬로우 쿼리 로깅"""
    start = time.perf_counter()

    try:
        result = await session.run(query, params or {})
        records = [record.data() async for record in result]
        duration_ms = int((time.perf_counter() - start) * 1000)

        if duration_ms > NEO4J_SLOW_THRESHOLD_MS:
            logger.warning(
                "neo4j_query_slow",
                duration_ms=duration_ms,
                query=query[:300],
                result_count=len(records),
            )
        else:
            logger.debug(
                "neo4j_query_completed",
                duration_ms=duration_ms,
                result_count=len(records),
            )

        return records
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(
            "neo4j_query_failed",
            duration_ms=duration_ms,
            query=query[:300],
            error=str(e),
        )
        raise
```

### 4.3 슬로우 쿼리 대응 절차

```
1. 감지
   ├── 자동: logging-system.md의 db_query_slow / neo4j_query_slow 이벤트
   ├── 자동: Prometheus api_request_duration_seconds p95 > SLO
   └── 수동: pg_stat_statements TOP 10 리뷰 (주 1회)

2. 분석
   ├── EXPLAIN ANALYZE 실행 (PostgreSQL)
   ├── PROFILE 실행 (Neo4j)
   ├── 실행 계획에서 Seq Scan, Nested Loop 확인
   └── AI 로그 분석 챗봇에 "슬로우 쿼리 분석" 요청

3. 대응
   ├── 인덱스 추가/수정
   │   ├── PostgreSQL: CREATE INDEX CONCURRENTLY (서비스 중단 없음)
   │   └── Neo4j: CREATE INDEX (온라인)
   ├── 쿼리 최적화
   │   ├── N+1 제거 (joinedload/selectinload)
   │   ├── 불필요 컬럼 제거 (SELECT *)
   │   └── 페이지네이션 적용 (LIMIT/OFFSET → Keyset)
   ├── 캐시 적용 (Redis L2)
   └── Materialized View 추가 (반복 집계)

4. 검증
   ├── EXPLAIN ANALYZE 재실행 → 실행 계획 비교
   ├── Prometheus 지연 메트릭 변화 확인
   └── K6 회귀 테스트
```

---

## 5. 커넥션 풀 관리

### 5.1 PostgreSQL 커넥션 풀 (SQLAlchemy)

```python
# app/core/database.py

from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,         # 기본: 20
    max_overflow=settings.DB_MAX_OVERFLOW,    # 기본: 80
    pool_recycle=settings.DB_POOL_RECYCLE,    # 기본: 3600초 (1시간)
    pool_pre_ping=True,                       # 연결 유효성 사전 확인
    pool_timeout=30,                          # 풀에서 연결 대기 최대 시간
    echo=settings.LOG_LEVEL == "DEBUG",       # DEBUG 시 SQL 출력
)
```

| 설정 | 개발 | 스테이징 | 프로덕션 | 설명 |
|------|:----:|:-------:|:-------:|------|
| `DB_POOL_SIZE` | 5 | 10 | 20 | 상시 유지 커넥션 |
| `DB_MAX_OVERFLOW` | 10 | 40 | 80 | 피크 시 추가 커넥션 |
| `DB_POOL_RECYCLE` | 1800 | 3600 | 3600 | 커넥션 재생성 주기 |

### 5.2 Neo4j 커넥션 풀

```python
# app/core/neo4j_client.py

from neo4j import AsyncGraphDatabase

driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    max_connection_pool_size=50,     # 최대 커넥션
    connection_acquisition_timeout=30,
    max_transaction_retry_time=15,
)
```

### 5.3 Redis 커넥션 풀

```python
# app/core/redis_client.py

import redis.asyncio as redis

redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=settings.REDIS_MAX_CONNECTIONS,  # 기본: 50
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
)
```

### 5.4 커넥션 풀 모니터링

```python
# app/core/metrics.py (Prometheus 메트릭)

# PostgreSQL
core_db_pool_size = Gauge("core_db_pool_size", "Pool size configured")
core_db_pool_active = Gauge("core_db_pool_active_connections", "Active connections")
core_db_pool_overflow = Gauge("core_db_pool_overflow", "Overflow connections in use")
core_db_pool_checkedout = Gauge("core_db_pool_checkedout", "Checked out connections")

# 주기적 메트릭 업데이트
async def update_pool_metrics():
    pool = engine.pool
    core_db_pool_size.set(pool.size())
    core_db_pool_active.set(pool.checkedin() + pool.checkedout())
    core_db_pool_overflow.set(pool.overflow())
    core_db_pool_checkedout.set(pool.checkedout())
```

---

## 6. DB 로그 이벤트 체계

로그 이벤트는 `logging-system.md`의 구조화 로깅 표준을 따른다.

### 6.1 DB 관련 로그 이벤트 목록

| 이벤트 | 레벨 | 서비스 | 설명 |
|--------|------|--------|------|
| `db_query_slow` | WARNING | 전체 | PostgreSQL 슬로우 쿼리 (> 1s) |
| `db_query_failed` | ERROR | 전체 | DB 쿼리 실패 |
| `db_pool_exhausted` | ERROR | 전체 | 커넥션 풀 소진 |
| `db_pool_overflow` | WARNING | 전체 | 오버플로우 커넥션 사용 중 |
| `db_connection_failed` | CRITICAL | 전체 | DB 연결 실패 |
| `db_migration_started` | INFO | Core | Alembic 마이그레이션 시작 |
| `db_migration_completed` | INFO | Core | 마이그레이션 완료 |
| `db_migration_failed` | ERROR | Core | 마이그레이션 실패 |
| `neo4j_query_slow` | WARNING | Oracle/Synapse/Weaver | Neo4j 슬로우 쿼리 (> 500ms) |
| `neo4j_query_failed` | ERROR | Oracle/Synapse/Weaver | Neo4j 쿼리 실패 |
| `neo4j_connection_failed` | CRITICAL | Oracle/Synapse/Weaver | Neo4j 연결 실패 |
| `redis_connection_failed` | CRITICAL | 전체 | Redis 연결 실패 |
| `redis_command_slow` | WARNING | 전체 | Redis 슬로우 명령 (> 100ms) |
| `mv_refresh_completed` | INFO | Vision | MV 갱신 완료 |
| `mv_refresh_failed` | ERROR | Vision | MV 갱신 실패 |
| `outbox_cleanup_completed` | INFO | Core | Event Outbox 정리 완료 |
| `backup_completed` | INFO | 인프라 | 백업 완료 |
| `backup_failed` | CRITICAL | 인프라 | 백업 실패 |

### 6.2 DB 관련 Prometheus 알림

`performance-monitoring.md` §4의 기존 알림에 추가:

```yaml
# alertmanager/rules/axiom-db-alerts.yml

groups:
  - name: axiom-database
    rules:
      # PostgreSQL 슬로우 쿼리 빈발
      - alert: HighSlowQueryRate
        expr: |
          sum(rate(core_db_slow_queries_total[10m])) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "슬로우 쿼리 10분간 {{ $value }}건/분 - 쿼리 최적화 필요"

      # PostgreSQL Dead Tuple 과다 (VACUUM 필요)
      - alert: HighDeadTuples
        expr: |
          pg_stat_user_tables_n_dead_tup{relname="event_outbox"} > 100000
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "event_outbox dead tuple {{ $value }}건 - VACUUM 필요"

      # PostgreSQL 디스크 사용률
      - alert: DBDiskUsageHigh
        expr: |
          (pg_database_size_bytes / (100 * 1024 * 1024 * 1024)) > 0.80
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL 디스크 사용률 80% - 용량 확장 필요"

      # Neo4j Heap 사용률
      - alert: Neo4jHeapHigh
        expr: |
          neo4j_heap_memory_used_bytes / neo4j_heap_memory_max_bytes > 0.85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Neo4j Heap {{ $value | humanizePercentage }} - 메모리 증설 검토"

      # 백업 실패
      - alert: BackupFailed
        expr: |
          axiom_backup_last_success_timestamp < (time() - 86400 * 2)
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "DB 백업 2일 이상 미실행 - 즉시 확인"
```

---

## 7. 재해복구 (DR) 계획

### 7.1 장애 시나리오별 복구

| 시나리오 | RPO | RTO | 복구 방법 |
|---------|:---:|:---:|----------|
| **PostgreSQL 인스턴스 장애** | 5분 | 30분 | RDS 자동 장애조치 (Multi-AZ, 1년 후 도입) |
| **PostgreSQL 데이터 손상** | 5분 | 30분 | RDS Point-in-Time Recovery |
| **PostgreSQL 잘못된 마이그레이션** | 0 | 10분 | Alembic downgrade -1 (배포 전 스냅샷 복원) |
| **Neo4j 인스턴스 장애** | 24시간 | 1시간 | S3 dump → 새 인스턴스 load |
| **Neo4j 데이터 손상** | 24시간 | 1시간 | 최신 dump 복원 |
| **Redis 인스턴스 장애** | N/A | 5분 | ElastiCache 자동 복구 + 캐시 워밍 |
| **Redis 데이터 유실** | N/A | 0 | 캐시 자동 재생성 (cold start) |
| **전체 리전 장애** | 24시간 | 4시간 | S3 교차 리전 복제 → 수동 복구 |

### 7.2 복구 절차 체크리스트

```
PostgreSQL 복구:
  □ 1. 장애 원인 파악 (RDS 이벤트, CloudWatch)
  □ 2. 스냅샷/PITR 대상 시점 결정
  □ 3. RDS 복원 실행 (새 인스턴스)
  □ 4. 보안 그룹 / 파라미터 그룹 적용
  □ 5. pg_stat_statements 리셋 (새 인스턴스)
  □ 6. 애플리케이션 DATABASE_URL 업데이트
  □ 7. RLS 정책 동작 확인
  □ 8. 서비스 헬스 체크 확인
  □ 9. 원본 인스턴스 삭제 (확인 후)

Neo4j 복구:
  □ 1. 최신 S3 dump 다운로드
  □ 2. 새 Neo4j Pod 배포 (StatefulSet)
  □ 3. neo4j-admin database load
  □ 4. 인덱스/제약조건 확인 (SHOW INDEXES, SHOW CONSTRAINTS)
  □ 5. 벡터 인덱스 ONLINE 상태 확인
  □ 6. 서비스 연결 확인 (Oracle, Synapse, Weaver)
  □ 7. FabricSnapshot 무결성 확인
```

---

## 8. 관리자 대시보드 DB 모니터링 연동

`admin-dashboard.md` §3의 시스템 모니터링 화면에서 표시하는 DB 메트릭:

### 8.1 Admin API 엔드포인트

```python
# app/api/admin/db_admin.py

from fastapi import APIRouter, Depends
from app.core.auth import require_role

router = APIRouter(prefix="/admin/db", tags=["admin"])

@router.get("/health")
async def get_db_health(_=Depends(require_role("admin"))):
    """DB 상태 종합 조회"""
    return {
        "postgres": {
            "status": "healthy",
            "version": "15.4",
            "connections": {"active": 15, "idle": 5, "max": 100},
            "disk_usage_percent": 45,
            "uptime_hours": 360,
            "replication_lag_ms": None,  # Single-AZ
        },
        "neo4j": {
            "status": "healthy",
            "version": "5.15",
            "heap_usage_percent": 65,
            "node_count": 45000,
            "relationship_count": 120000,
            "store_size_mb": 2048,
        },
        "redis": {
            "status": "healthy",
            "version": "7.2",
            "memory_usage_percent": 52,
            "connected_clients": 25,
            "ops_per_sec": 1200,
            "stream_lengths": {
                "axiom:events": 8500,
                "axiom:watches": 200,
                "axiom:workers": 50,
            },
        },
    }

@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = 10,
    _=Depends(require_role("admin"))
):
    """최근 슬로우 쿼리 TOP N"""
    # pg_stat_statements 조회
    ...

@router.get("/maintenance")
async def get_maintenance_status(_=Depends(require_role("admin"))):
    """유지보수 상태 조회"""
    return {
        "last_vacuum": {"event_outbox": "2026-02-20T04:00:00Z"},
        "last_analyze": {"cases": "2026-02-20T03:00:00Z"},
        "last_backup": {
            "postgres_snapshot": "2026-02-20T03:30:00Z",
            "neo4j_dump": "2026-02-20T04:00:00Z",
        },
        "last_mv_refresh": "2026-02-20T12:00:00Z",
        "outbox_pending": 12,
        "outbox_failed": 0,
        "dead_tuples": {"event_outbox": 2500, "watch_alerts": 800},
    }
```

### 8.2 관리자 화면 DB 패널

```
┌─ 시스템 모니터링 > 인프라 상태 ──────────────────────────────────┐
│                                                                    │
│  ┌─ PostgreSQL ────────────────────────────────────────────┐      │
│  │ ● 정상   v15.4   ap-northeast-2                         │      │
│  │                                                          │      │
│  │ 커넥션: 15/100 (15%)   디스크: 45/100GB (45%)           │      │
│  │ 슬로우 쿼리: 3건/시간  Dead Tuple: 2,500 (outbox)       │      │
│  │                                                          │      │
│  │ 최근 백업: 5시간 전 ✓  최근 VACUUM: 10시간 전 ✓         │      │
│  │ Outbox: Pending 12건, Failed 0건                         │      │
│  │                                                          │      │
│  │ [슬로우 쿼리 TOP 10] [RDS Performance Insights →]       │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌─ Neo4j ─────────────────────────────────────────────────┐      │
│  │ ● 정상   v5.15   EKS StatefulSet                        │      │
│  │                                                          │      │
│  │ Heap: 3.2/4GB (80%)   Store: 2GB                        │      │
│  │ 노드: 45,000   관계: 120,000                            │      │
│  │ 인덱스: 12/12 ONLINE   벡터 인덱스: 2 ONLINE            │      │
│  │                                                          │      │
│  │ 최근 백업: 10시간 전 ✓                                  │      │
│  │                                                          │      │
│  │ [쿼리 로그] [인덱스 상태]                                │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌─ Redis ─────────────────────────────────────────────────┐      │
│  │ ● 정상   v7.2   ElastiCache r6g.large                   │      │
│  │                                                          │      │
│  │ 메모리: 2.1/4GB (52%)   OPS: 1,200/s                   │      │
│  │ 클라이언트: 25                                           │      │
│  │                                                          │      │
│  │ Streams:                                                 │      │
│  │   axiom:events  8,500/10,000  Consumer lag: 0            │      │
│  │   axiom:watches   200/10,000  Consumer lag: 0            │      │
│  │   axiom:workers    50/10,000  Consumer lag: 0            │      │
│  │                                                          │      │
│  │ [메모리 분석] [Slow Log]                                 │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 9. 데이터 보관 정책 통합 뷰

`data-lifecycle.md`와 `logging-system.md`의 보관 정책을 통합 정리한다.

| 데이터 유형 | 저장소 | 보관 기간 | 정리 방법 | 근거 |
|------------|--------|:---------:|----------|------|
| 케이스/프로세스 | PostgreSQL | 10년 | S3 아카이빙 | 규정 의무 |
| 워크아이템/결과 | PostgreSQL | 영구 | 보존 | 감사 추적 |
| Event Outbox (PUBLISHED) | PostgreSQL | 7일 | pg_cron 삭제 | 디버깅 |
| Event Outbox (FAILED) | PostgreSQL | 30일 | pg_cron 삭제 | 디버깅 |
| Watch 알림 (acknowledged) | PostgreSQL | 90일 | pg_cron 삭제 | 알림 이력 |
| LLM 호출 로그 | PostgreSQL | 30일 | pg_cron 삭제 | 비용 분석 |
| Neo4j 메타데이터 | Neo4j | 영구 | FabricSnapshot 버전 관리 | 스키마 메타 |
| Redis 캐시 | Redis | TTL 기반 | 자동 만료 | 캐시 |
| Redis Streams | Redis | MAXLEN 10,000 | 자동 트림 | 메모리 |
| 멱등성 키 | Redis | 7일 TTL | 자동 만료 | 이벤트 중복 방지 |
| 세션 | Redis | 7일 TTL | 자동 만료 | 인증 |
| 애플리케이션 로그 | Loki/CloudWatch | 7일 | 자동 삭제 | 운영 |
| 감사 로그 | S3 Glacier | 1년 | Lifecycle | 컴플라이언스 |
| DB 자동 백업 (RDS) | RDS | 7일 | 자동 | 복구 |
| DB 수동 스냅샷 | RDS | 30일 | 수동 삭제 | 배포 보호 |
| Neo4j dump | S3 | 7일 | CronJob 삭제 | 복구 |
| Prometheus 메트릭 | Prometheus/Thanos | 30일/1년 | 자동 | 모니터링 |

---

## 결정 사항 (Decisions)

- PostgreSQL 백업은 RDS 자동 백업(7일 PITR) + 배포 전 수동 스냅샷
  - 근거: RDS 관리형 백업으로 운영 부담 최소화

- Neo4j 백업은 일일 dump + S3 저장
  - 근거: Community Edition 온라인 백업 미지원, dump가 가장 안정적
  - 재평가: Enterprise 전환 시 온라인 백업으로 변경

- Redis는 별도 백업하지 않음
  - 근거: 모든 데이터가 재생성 가능 (캐시, 임시 데이터)

- 슬로우 쿼리 임계값: PostgreSQL 1초, Neo4j 500ms
  - 근거: SLO 기준 (Core API p95 < 500ms)

- pg_cron으로 데이터 정리 자동화
  - 근거: 별도 배치 서비스 불필요, RDS 네이티브 지원

## 금지됨 (Forbidden)

- 프로덕션 DB에 직접 DDL 실행 (반드시 Alembic 경유)
- 백업 미수행 상태로 마이그레이션 실행
- Neo4j에 패스워드 저장 (connection-security.md 정책)
- VACUUM FULL 운영 시간 실행 (테이블 락 발생)
- pg_stat_statements 리셋 없이 슬로우 쿼리 분석 (누적 편향)

## 필수 (Required)

- 배포 전 반드시 DB 스냅샷 생성
- 월 1회 백업 복원 테스트 실행
- 슬로우 쿼리 주간 리뷰 (pg_stat_statements TOP 10)
- 마이그레이션은 upgrade + downgrade 양방향 작성

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `06_data/database-schema.md` | Core PostgreSQL 스키마 원본 |
| `06_data/data-lifecycle.md` | 엔티티별 라이프사이클, Alembic 전략 |
| `06_data/event-outbox.md` | Event Outbox + Redis Streams 상세 |
| `08_operations/performance-monitoring.md` | DB 메트릭, 커넥션 풀 알림, 용량 계획 |
| `08_operations/logging-system.md` | DB 로그 이벤트 (db_query_slow 등), AI 분석 |
| `08_operations/configuration.md` | DB_POOL_SIZE 등 환경변수 |
| `services/vision/docs/06_data/database-schema.md` | Vision PostgreSQL 스키마 |
| `services/vision/docs/06_data/data-warehouse.md` | MV Star Schema |
| `services/weaver/docs/06_data/neo4j-schema-v2.md` | Neo4j v2 스키마 |
| `services/synapse/docs/06_data/neo4j-schema.md` | Synapse Neo4j 스키마 |
| `services/weaver/docs/07_security/connection-security.md` | DB 연결 보안 |
| `apps/canvas/docs/04_frontend/admin-dashboard.md` | 관리자 UI DB 모니터링 화면 |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 (백업, 유지보수, 슬로우 쿼리, DR, 관리자 연동) |
