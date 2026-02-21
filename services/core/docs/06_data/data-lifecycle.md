# Axiom Core - 데이터 라이프사이클

## 이 문서가 답하는 질문

- 주요 데이터 엔티티의 생성 -> 사용 -> 폐기 흐름은 어떠한가?
- 데이터 보존 정책은 무엇인가?
- 데이터 마이그레이션(Alembic) 전략은 어떻게 운영되는가?

<!-- affects: backend, operations -->
<!-- requires-update: 06_data/database-schema.md -->

---

## 1. 엔티티별 라이프사이클

### 1.1 케이스(Case)

```
생성: 프로세스 분석가가 Canvas UI에서 프로젝트 생성
  |
사용: 데이터 등록, 분석 보고서, 최적화 시나리오 등 모든 프로세스의 루트 엔티티
  |   - 프로세스 인스턴스 연결 (bpm_proc_inst.case_id)
  |   - 문서 연결 (documents.case_id)
  |   - 알림 연결 (watch_alerts.case_id)
  |
보관: 프로젝트 종결 시 status='CLOSED'로 변경 (데이터는 보존)
  |
폐기: 규정 보존 기간(10년) 경과 후 아카이빙 (삭제가 아닌 별도 스토리지 이동)
```

### 1.2 워크아이템(Workitem)

```
생성: BPM 엔진이 Activity에 따라 자동 생성 (status=TODO)
  |
사용: 에이전트/사용자가 작업 수행
  |   TODO -> IN_PROGRESS -> SUBMITTED -> DONE
  |
보존: 완료된 워크아이템은 감사 목적으로 영구 보존
  |   result_data, draft_data, confidence 모두 기록
  |
참조: 지식 학습 시 과거 워크아이템의 결과를 참조
```

### 1.3 Event Outbox

```
생성: 비즈니스 로직 실행 시 같은 트랜잭션에서 INSERT (status=PENDING)
  |
처리: Sync Worker가 폴링하여 Redis Streams로 발행 (status=PUBLISHED)
  |
보존: 7일간 보존 후 자동 삭제 (PUBLISHED 상태)
  |   FAILED 상태는 30일간 보존 (디버깅 목적)
  |
정리: pg_cron으로 주기적 정리
      DELETE FROM event_outbox WHERE status = 'PUBLISHED' AND published_at < now() - interval '7 days'
```

---

## 2. 데이터 보존 정책

| 데이터 유형 | 보존 기간 | 근거 | 정리 방법 |
|------------|----------|------|----------|
| 케이스 데이터 | 10년 | 규정 의무 보존 | 아카이빙 (S3) |
| 워크아이템 | 영구 | 감사 추적 | 보존 |
| 프로세스 인스턴스 | 영구 | 감사 추적 | 보존 |
| Event Outbox (PUBLISHED) | 7일 | 디버깅 | pg_cron 자동 삭제 |
| Event Outbox (FAILED) | 30일 | 디버깅 | pg_cron 자동 삭제 |
| Watch 알림 (acknowledged) | 90일 | 알림 이력 | pg_cron 자동 삭제 |
| Redis Streams | MAXLEN 10000 | 메모리 관리 | Redis 자동 관리 |
| LLM 호출 로그 | 30일 | 비용 분석 | pg_cron 자동 삭제 |

---

## 3. 마이그레이션 전략

### 3.1 제약/인덱스 마이그레이션

```
[결정] 제약/인덱스 변경은 버전 스크립트로 관리한다.
[근거] 현재 Core 저장소에는 Alembic 디렉터리가 없으므로, 운영 반영 가능한 독립 스크립트를 우선 사용한다.

명령어:
  DATABASE_URL=postgresql+asyncpg://... python3 services/core/scripts/migrate_constraints_v1.py

스크립트 위치:
  services/core/scripts/migrate_constraints_v1.py
```

### 3.2 마이그레이션 규칙

```
[필수] 모든 스키마 변경은 버전 스크립트 또는 정식 마이그레이션 도구를 통해 관리한다.
[필수] 스크립트는 idempotent 하게 작성한다 (`IF NOT EXISTS`, `DO $$ ... $$`).
[필수] 대량 데이터 마이그레이션은 별도 스크립트로 분리한다.
[금지] 프로덕션 DB에 수동 DDL 실행 (스크립트 없이 직접 실행 금지).
[금지] 마이그레이션에서 데이터 삭제 (DROP COLUMN 등은 별도 검토 후 적용).
```

---

## 근거

- K-AIR process-gpt-main/init.sql (95KB 단일 파일의 한계)
- K-AIR 역설계 보고서 섹션 13.2 (데이터 모델 결정)
- [06_data/database-operations.md](./database-operations.md) (pg_cron 자동 정리, 백업/복구 전략, 보관 정책 통합 뷰)
