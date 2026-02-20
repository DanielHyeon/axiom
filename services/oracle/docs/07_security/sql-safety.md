# SQL 안전성 정책

## 이 문서가 답하는 질문

- Oracle의 SQL 실행에 대한 보안 정책은 무엇인가?
- 어떤 SQL이 허용되고, 어떤 SQL이 차단되는가?
- DB 접근 계정의 권한 수준은?
- 감사 로깅은 어떻게 동작하는가?

<!-- affects: 01_architecture, 02_api, 03_backend -->
<!-- requires-update: 01_architecture/sql-guard.md, 03_backend/sql-execution.md -->

---

## 1. 보안 원칙

Oracle의 SQL 안전성은 **3중 방어**(Defense in Depth) 원칙을 따른다:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: SQL Guard (애플리케이션 레벨)                  │
│  - 금지 키워드 차단                                      │
│  - SQLGlot 파싱 검증                                     │
│  - 구조적 제약 (JOIN/서브쿼리 깊이)                      │
│  - LIMIT 강제                                            │
├─────────────────────────────────────────────────────────┤
│  Layer 2: DB 계정 권한 (데이터베이스 레벨)               │
│  - SELECT-only 계정 (DML/DDL 불가)                       │
│  - 스키마 단위 접근 제어                                 │
│  - statement_timeout 설정                                │
├─────────────────────────────────────────────────────────┤
│  Layer 3: 네트워크 격리 (인프라 레벨)                    │
│  - Oracle -> Target DB만 허용 (단방향)                   │
│  - VPC 내부 통신만 허용                                  │
│  - SSL/TLS 암호화 통신                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. SQL 허용/차단 규칙

### 2.1 허용 (Allowed)

| 항목 | 조건 |
|------|------|
| SELECT 문 | 단일 SELECT만 허용 |
| JOIN | 최대 5개 테이블 (max_join_depth) |
| 서브쿼리 | 최대 3단계 중첩 (max_subquery_depth) |
| 집계 함수 | COUNT, SUM, AVG, MIN, MAX, GROUP BY |
| 날짜 함수 | EXTRACT, DATE_TRUNC, YEAR, MONTH 등 |
| 문자열 함수 | UPPER, LOWER, TRIM, SUBSTRING, CONCAT |
| 조건절 | WHERE, HAVING, CASE WHEN, COALESCE |
| 정렬/제한 | ORDER BY, LIMIT, OFFSET |
| 집합 연산 | UNION, UNION ALL (최대 5개) |
| 윈도우 함수 | ROW_NUMBER, RANK, LAG, LEAD 등 |

### 2.2 차단 (Forbidden)

| 항목 | 차단 이유 |
|------|----------|
| INSERT, UPDATE, DELETE, MERGE | 데이터 변경 방지 |
| CREATE, ALTER, DROP, TRUNCATE | 스키마 변경 방지 |
| GRANT, REVOKE | 권한 변경 방지 |
| EXEC, EXECUTE, xp_cmdshell | 시스템 명령 실행 방지 |
| SLEEP, BENCHMARK | DoS 공격 방지 |
| LOAD_FILE, INTO OUTFILE | 파일 시스템 접근 방지 |
| information_schema, pg_catalog | 시스템 카탈로그 접근 방지 |
| SQL 주석 (--, /* */) | 주석 기반 인젝션 방지 |
| 다중 SQL 문 (;) | 배치 인젝션 방지 |

---

## 3. DB 접근 계정

### 3.1 계정 설정

```sql
-- Oracle 전용 읽기 전용 계정 생성
CREATE USER oracle_reader WITH PASSWORD '${ORACLE_DB_PASSWORD}';

-- SELECT 권한만 부여
GRANT CONNECT ON DATABASE business_db TO oracle_reader;
GRANT USAGE ON SCHEMA public TO oracle_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO oracle_reader;

-- 향후 생성되는 테이블에도 자동 SELECT 부여
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO oracle_reader;

-- 명시적 DML 금지 (이중 방어)
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM oracle_reader;

-- statement_timeout 설정 (DB 레벨)
ALTER USER oracle_reader SET statement_timeout = '30s';

-- 최대 커넥션 수 제한
ALTER USER oracle_reader CONNECTION LIMIT 15;
```

### 3.2 계정 권한 요약

| 권한 | 허용 | 설명 |
|------|------|------|
| CONNECT | Yes | DB 연결 |
| SELECT | Yes | 데이터 조회 |
| INSERT | **No** | 데이터 삽입 차단 |
| UPDATE | **No** | 데이터 수정 차단 |
| DELETE | **No** | 데이터 삭제 차단 |
| CREATE | **No** | 객체 생성 차단 |
| ALTER | **No** | 객체 변경 차단 |
| DROP | **No** | 객체 삭제 차단 |
| TEMP | **No** | 임시 테이블 생성 차단 |

---

## 4. 감사 로깅

### 4.1 로깅 대상

| 이벤트 | 로그 레벨 | 기록 정보 |
|--------|----------|----------|
| SQL 생성 | INFO | question, generated_sql, tables_used |
| SQL Guard PASS | DEBUG | sql, guard_status |
| SQL Guard REJECT | WARN | sql, violations, user_id |
| SQL 실행 성공 | INFO | sql, execution_time, row_count |
| SQL 실행 에러 | ERROR | sql, error_message, user_id |
| SQL 타임아웃 | WARN | sql, timeout_seconds, user_id |
| 직접 SQL 실행 | WARN | sql, user_id (항상 기록) |
| 화이트리스트 위반 | ERROR | sql, unauthorized_tables, user_id |

### 4.2 로그 형식

```json
{
    "timestamp": "2024-01-15T09:30:00.123Z",
    "level": "WARN",
    "service": "oracle",
    "event": "sql_guard_reject",
    "data": {
        "question": "프로세스 데이터 전부 삭제해줘",
        "generated_sql": "DELETE FROM process_metrics",
        "violations": ["금지 키워드 발견: DELETE"],
        "user_id": "user_001",
        "datasource_id": "ds_business_main",
        "ip_address": "10.0.1.15"
    }
}
```

### 4.3 로깅 규칙

**필수 (Required)**:
- 모든 SQL Guard REJECT는 WARN 이상으로 기록
- 모든 직접 SQL 실행은 WARN으로 기록 (관리자 행위 추적)
- 화이트리스트 위반은 ERROR로 기록 (잠재적 공격 시도)

**금지 (Forbidden)**:
- SQL 실행 결과 데이터를 로그에 포함하지 않음 (민감 데이터 보호)
- DB 접속 정보(비밀번호, 커넥션 문자열)를 로그에 포함하지 않음
- 사용자 PII(개인식별정보)를 user_id 외에 로그에 포함하지 않음

---

## 5. 실행 제한

| 제한 항목 | 값 | 적용 위치 | 근거 |
|----------|-----|---------|------|
| SQL 타임아웃 | 30초 | SQL Guard + DB | 과도한 쿼리 실행 방지 |
| 최대 행 수 | 10,000행 | SQL Executor | 메모리 보호 |
| 응답 행 수 | 1,000행 | API 응답 | 네트워크 대역폭 보호 |
| LIMIT 강제 | 자동 추가 | SQL Guard | 풀 스캔 방지 |
| JOIN 깊이 | 5개 | SQL Guard | 복잡도 폭발 방지 |
| 서브쿼리 깊이 | 3단계 | SQL Guard | 복잡도 폭발 방지 |
| Rate Limit | 30/분 | API Gateway | DDoS 방지 |

---

## 6. 위협 모델

| 위협 | 공격 벡터 | 방어 |
|------|----------|------|
| SQL 인젝션 | 자연어에 SQL 구문 삽입 | SQL Guard Layer 1 (키워드) |
| 프롬프트 인젝션 | LLM에 악의적 지시 주입 | 입력 검증 + 역할 고정 |
| 데이터 유출 | 대량 SELECT로 데이터 추출 | LIMIT 강제 + Rate Limit |
| DoS | 과도한 쿼리 요청 | 타임아웃 + Rate Limit |
| 권한 상승 | DDL/DCL 실행 시도 | SQL Guard + DB 계정 권한 |
| 시스템 정보 노출 | information_schema 접근 | 키워드 차단 + 계정 권한 |

---

## 7. 비즈니스 데이터 보안

### 7.1 민감 데이터 분류

| 민감도 | 데이터 유형 | 예시 |
|--------|-----------|------|
| **높음** | 대상 조직 개인정보 | 이름, 주소, 사업자번호 |
| **높음** | 재무 상세 | 개별 거래 금액 |
| **중간** | 프로세스 상태 | 진행 상황 |
| **낮음** | 통계 데이터 | 연도별 건수, 조직별 통계 |

### 7.2 확정 구현 정책

| 기능 | 설명 | 정책 |
|------|------|------|
| 컬럼 레벨 마스킹 | 민감 컬럼의 값을 마스킹 출력 | `name/address/registration_no/account_no`는 역할별 동적 마스킹 적용 |
| 역할 기반 테이블 접근 | 사용자 역할에 따라 조회 가능 테이블 제한 | `oracle.table_acl` allowlist 기반. `admin`만 전체 접근 |
| 결과 행 수 제한 (사용자별) | 역할에 따라 다른 행 수 제한 | `admin=5000`, `manager/attorney=2000`, `analyst/engineer=1000`, `staff/viewer=300` |

#### 7.2.1 마스킹 규칙

| 컬럼 패턴 | 마스킹 예시 | 허용 역할 |
|----------|-----------|----------|
| `*_name` | `홍*동` | admin, manager, attorney |
| `*address*` | `서울시 ***` | admin, manager |
| `*registration_no*` | `123-45-*****` | admin |
| `*account*` | `110-***-*****` | admin |

#### 7.2.2 적용 위치

- SQL Guard 후처리: SELECT projection에 마스킹 함수 자동 적용
- SQL Executor: 역할별 row_limit 강제 (요청값이 더 작으면 요청값 우선)
- Audit Log: 마스킹 적용 여부(`masking_applied=true/false`) 필수 기록

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 3중 방어 | 단일 레이어 실패 시에도 안전 |
| SELECT-only DB 계정 | 가장 근본적인 DML 방지 |
| 감사 로깅 필수 | 보안 사고 시 추적 가능성 |
| 결과 데이터 로그 제외 | 민감 데이터 로그 유출 방지 |

## 금지 사항

- SQL Guard를 우회하는 코드 경로 생성 금지
- DB 계정에 SELECT 이외 권한 부여 금지
- 감사 로그 비활성화 금지
- 민감 데이터를 로그에 포함 금지

## 관련 문서

- [01_architecture/sql-guard.md](../01_architecture/sql-guard.md): SQL Guard 상세
- [03_backend/sql-execution.md](../03_backend/sql-execution.md): SQL 실행 엔진
- [08_operations/deployment.md](../08_operations/deployment.md): DB 계정 설정
