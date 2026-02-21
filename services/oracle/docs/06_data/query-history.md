# 쿼리 이력 스키마

## 이 문서가 답하는 질문

- 쿼리 이력은 어디에 저장되는가?
- K-AIR(SQLite) 레거시와 Axiom(PostgreSQL) 스키마는 무엇이 다른가?
- 이력 데이터의 보존 정책은?

<!-- affects: 02_api, 03_backend -->
<!-- requires-update: 02_api/feedback-api.md -->

---

## 1. 레거시 참고: SQLite (K-AIR 원본)

K-AIR `history.py`는 과거 SQLite를 사용했다. Axiom Oracle의 저장소 표준은 PostgreSQL이다.

### 1.1 SQLite 스키마

```sql
CREATE TABLE query_history (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'success',  -- success | error
    result_json TEXT,                         -- JSON 직렬화된 결과
    error_message TEXT,
    execution_time_ms INTEGER,
    row_count INTEGER,
    datasource_id TEXT NOT NULL,
    user_id TEXT,
    tables_used TEXT,                         -- JSON 배열
    cache_hit BOOLEAN DEFAULT FALSE,
    guard_status TEXT,                        -- PASS | FIX | REJECT
    guard_fixes TEXT,                         -- JSON 배열
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE query_feedback (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL REFERENCES query_history(id),
    rating TEXT NOT NULL,                     -- positive | negative | partial
    corrected_sql TEXT,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_history_datasource ON query_history(datasource_id);
CREATE INDEX idx_history_created ON query_history(created_at);
CREATE INDEX idx_history_user ON query_history(user_id);
CREATE INDEX idx_feedback_query ON query_feedback(query_id);
```

### 1.2 SQLite의 한계

| 한계 | 영향 |
|------|------|
| 동시 쓰기 불가 | 다중 요청 시 WAL 잠금 충돌 |
| 파일 기반 | 컨테이너 재시작 시 데이터 손실 (볼륨 필요) |
| 쿼리 기능 제한 | 복잡한 집계/분석 쿼리 불편 |
| 백업/복구 | 파일 복사 의존 |

---

## 2. 현재 표준: PostgreSQL (Axiom)

### 2.1 PostgreSQL 스키마

```sql
-- Oracle 서비스 전용 스키마
CREATE SCHEMA IF NOT EXISTS oracle;

CREATE TABLE oracle.query_history (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'success'
        CHECK (status IN ('success', 'error')),
    result_json JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    row_count INTEGER,
    datasource_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100),
    tables_used TEXT[],                       -- PostgreSQL 배열
    cache_hit BOOLEAN DEFAULT FALSE,
    guard_status VARCHAR(20),
    guard_fixes TEXT[],
    pipeline_steps JSONB,                     -- 각 단계별 소요시간
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 파티셔닝 지원
    CONSTRAINT pk_history PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 월별 파티션 (자동 생성 필요)
CREATE TABLE oracle.query_history_2024_01
    PARTITION OF oracle.query_history
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE oracle.query_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL,
    query_created_at TIMESTAMPTZ NOT NULL,
    rating VARCHAR(20) NOT NULL
        CHECK (rating IN ('positive', 'negative', 'partial')),
    corrected_sql TEXT,
    comment TEXT,
    user_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_feedback_query
        FOREIGN KEY (query_id, query_created_at)
        REFERENCES oracle.query_history(id, created_at)
);

-- 인덱스
CREATE INDEX idx_history_datasource
    ON oracle.query_history(datasource_id, created_at DESC);
CREATE INDEX idx_history_user
    ON oracle.query_history(user_id, created_at DESC);
CREATE INDEX idx_history_status
    ON oracle.query_history(status) WHERE status = 'error';
CREATE INDEX idx_feedback_query
    ON oracle.query_feedback(query_id);

-- 전문 검색 인덱스 (질문 검색용)
CREATE INDEX idx_history_question_search
    ON oracle.query_history
    USING gin(to_tsvector('simple', question));
```

### 2.2 변경 사항 요약

| 항목 | SQLite (K-AIR) | PostgreSQL (Axiom) |
|------|---------------|-------------------|
| ID 타입 | TEXT (수동 생성) | UUID (자동 생성) |
| JSON 저장 | TEXT (직렬화) | JSONB (네이티브) |
| 배열 저장 | TEXT (JSON) | TEXT[] (네이티브) |
| 시간대 | TIMESTAMP (로컬) | TIMESTAMPTZ (UTC) |
| 동시성 | WAL (제한적) | MVCC (완전) |
| 파티셔닝 | 불가 | 월별 파티션 |
| 전문 검색 | 불가 | GIN 인덱스 |
| 스키마 | 단일 DB | `oracle` 스키마 격리 |

---

## 3. 데이터 보존 정책

| 정책 | 값 | 근거 |
|------|-----|------|
| 이력 보존 기간 | 1년 | 비즈니스 분석 주기 기준 |
| 파티션 유지 | 12개월 | 월별 파티션 자동 생성/삭제 |
| 피드백 보존 | 영구 | 품질 개선 누적 데이터 |
| 에러 이력 보존 | 6개월 | 디버깅 목적 |

### 3.1 파티션 관리

```sql
-- 월별 파티션 자동 생성 (pg_partman 또는 cron job)
-- 매월 1일 실행
SELECT create_next_partition('oracle.query_history');

-- 1년 이상 된 파티션 삭제
DROP TABLE IF EXISTS oracle.query_history_2023_01;
```

---

## 4. 이관 절차 (레거시 참고)

> 기준일: 2026-02-21

| 단계 | 작업 | 상태 | 완료 기준 |
|------|------|------|----------|
| 1 | PostgreSQL 스키마 생성 | 설계 완료 | DDL 리뷰 통과 + 테스트 DB 적용 |
| 2 | Repository 패턴 구현 (SQLite/PG 추상화) | 부분 완료 | `query_history.py` mock 구현 + 실제 PostgreSQL 영속화 전환 |
| 3 | 기존 SQLite 데이터 마이그레이션 스크립트 | 구현 예정 | Dry-run/실행 로그/롤백 스크립트 준비 |
| 4 | PostgreSQL Repository로 전환 | 구현 예정 | mock 저장소 제거 + Read/Write 경로 전환 |
| 5 | SQLite 코드 제거 | 구현 예정 | 2주 무결성 검증 후 코드/의존성 제거 |

### 4.1 컷오버 전략

| 단계 | 기간 | 핵심 작업 | 실패 시 복구 |
|------|------|---------|------------|
| A. 스키마 배포 | D-7 | `oracle` 스키마/인덱스/파티션 생성 | DDL 롤백 |
| B. Dual-write | D-7 ~ D-1 | SQLite + PostgreSQL 동시 기록 | SQLite 단독 모드 복귀 |
| C. Read 전환 | D-day | 조회 API를 PostgreSQL 우선 조회로 전환 | Feature flag 즉시 롤백 |
| D. 정리 | D+14 | SQLite 파일/코드 제거 | 백업 파일 기반 복구 |

### 4.2 검증 체크리스트

- row_count, status, guard_status 필드가 소스/타깃에서 100% 일치
- 샘플 100건 SQL 재실행 시 실행 결과/오류 분류가 동일
- 피드백(`query_feedback`) FK 무결성 검증 통과

---

## 관련 문서

- [02_api/feedback-api.md](../02_api/feedback-api.md): 이력/피드백 API
- [08_operations/deployment.md](../08_operations/deployment.md): DB 설정
- [08_operations/migration-from-kair.md](../08_operations/migration-from-kair.md): 이식 가이드
