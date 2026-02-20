# Axiom Core - 데이터 격리

## 이 문서가 답하는 질문

- 테넌트 간 데이터 격리는 어떻게 보장되는가?
- RLS 정책은 어떤 테이블에 적용되고, 어떤 조건으로 필터링하는가?
- 격리가 실패하는 엣지 케이스와 대응 방안은 무엇인가?

<!-- affects: backend, data -->
<!-- requires-update: 06_data/database-schema.md -->

---

## 1. 4중 격리 모델

```
Layer 1: JWT - 토큰에 tenant_id 포함, 위조 불가
     |
Layer 2: ContextVar - 요청 스코프에서 tenant_id 격리
     |
Layer 3: RLS - DB 레벨에서 tenant_id 필터링 (최종 방어선)
     |
Layer 4: 쿼리 WHERE - 명시적 tenant_id 조건 (이중 안전)
```

### 1.1 왜 4중인가

```
[결정] RLS만으로도 충분하지만, Defense-in-Depth 원칙에 따라 4중 격리를 적용한다.
[근거] 1. JWT: 인증 단계에서 테넌트 확인 (1차 차단)
       2. ContextVar: 애플리케이션 로직에서 잘못된 테넌트 접근 방지 (2차 차단)
       3. RLS: DB 레벨에서 강제 필터링 (3차 차단, 개발자 실수 방지)
       4. WHERE: ORM 쿼리에 명시적 조건 (코드 가독성 + 디버깅)

어느 한 계층이 실패해도 다른 계층이 보호한다.
```

---

## 2. RLS 정책 상세

### 2.1 적용 대상 테이블

```sql
-- RLS가 적용되는 테이블 (tenant_id 컬럼이 있는 모든 테이블)
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE proc_def ENABLE ROW LEVEL SECURITY;
ALTER TABLE bpm_proc_inst ENABLE ROW LEVEL SECURITY;
ALTER TABLE bpm_work_item ENABLE ROW LEVEL SECURITY;
-- documents 테이블은 향후 문서 관리 기능 추가 시 생성 예정
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_alert_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 테넌트 테이블 자체는 admin만 접근 (RLS 별도)
-- tenants 테이블은 슈퍼유저/admin만 접근
```

### 2.2 정책 정의

```sql
-- 공통 정책: 현재 테넌트의 데이터만 조회/수정 가능
CREATE POLICY tenant_read ON cases
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_write ON cases
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_update ON cases
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_delete ON cases
    FOR DELETE
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

---

## 3. 엣지 케이스와 대응

| 엣지 케이스 | 위험 | 대응 |
|------------|------|------|
| Worker에서 ContextVar 미설정 | RLS 세션 변수가 빈 문자열 -> 빈 결과 반환 | Worker는 이벤트의 tenant_id를 명시적으로 세션에 설정 |
| 관리자 API에서 여러 테넌트 데이터 조회 | admin이 다른 테넌트 데이터 접근 | admin 전용 바이패스 정책 (별도 DB 역할) |
| DB 마이그레이션 시 RLS 미적용 | 새 테이블에 RLS 누락 | CI에서 RLS 적용 여부 자동 검사 스크립트 |
| Redis 캐시에 tenant_id 미포함 | 캐시 키에 tenant_id 없으면 다른 테넌트 데이터 노출 | 모든 Redis 키에 `{tenant_id}:` 접두어 |

---

## 4. 격리 규칙 요약

```
[필수] 모든 DB 테이블에 tenant_id 컬럼과 RLS 정책을 적용한다.
[필수] 모든 DB 세션 시작 시 SET app.current_tenant_id를 실행한다.
[필수] 모든 Redis 키에 tenant_id 접두어를 포함한다.
[필수] Worker는 이벤트 데이터에서 tenant_id를 추출하여 세션에 설정한다.
[필수] 새 테이블 생성 시 RLS 정책을 반드시 함께 추가한다.
[금지] RLS를 비활성화하는 쿼리 힌트 사용 (SET row_security = off 금지).
[금지] tenant_id를 사용자 입력에서 받지 않는다 (JWT에서만 추출).
```

---

## 근거

- K-AIR process-gpt-main/init.sql (RLS 정책)
- K-AIR process-gpt-completion-main (DBConfigMiddleware, ContextVar)
- ADR-003: ContextVar 기반 멀티테넌트
