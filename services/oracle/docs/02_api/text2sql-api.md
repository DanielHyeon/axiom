# NL2SQL API 스펙

## 이 문서가 답하는 질문

- NL2SQL 관련 API 엔드포인트의 정확한 요청/응답 형식은?
- 각 필드는 nullable인가?
- 어떤 권한이 필요한가?
- 에러 코드의 의미는?

<!-- affects: 04_frontend, 05_llm -->
<!-- requires-update: 01_architecture/nl2sql-pipeline.md -->

---

## 1. 엔드포인트 요약

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | `/text2sql/ask` | NL2SQL 단일 변환+실행+시각화 | Required |
| POST | `/text2sql/react` | ReAct 다단계 추론 (NDJSON 스트림) | Required |
| POST | `/text2sql/direct-sql` | SQL 직접 실행 | Required + Admin |

### 외부 의존성

NL2SQL 파이프라인은 Synapse Graph Layer (Neo4j)에 의존한다.

| 의존 대상 | 용도 | 호출 시점 |
|----------|------|----------|
| Synapse Graph API (Neo4j 벡터 검색) | 질문 임베딩 → 관련 테이블/컬럼 5축 검색 | `/ask`, `/react` 매 요청 |
| Synapse Graph API (FK 그래프 탐색) | 복잡한 조인 경로 자동 탐색 (최대 3홉) | SQL 생성 시 다중 테이블 JOIN 필요 시 |
| Synapse Graph API (Query 노드 영속화) | 품질 게이트 통과 쿼리 캐싱 | 신뢰도 ≥ 0.90인 결과 저장 시 |

- **Neo4j 불가 시**: 503 `NEO4J_UNAVAILABLE` 반환. 스키마 그래프 검색이 불가하므로 모든 NL2SQL 기능이 중단된다.
- **파이프라인 상세**: [nl2sql-pipeline.md](../01_architecture/nl2sql-pipeline.md) §2 Graph Search 참조.

---

## 2. POST /text2sql/ask

### 2.1 설명

자연어 질문을 SQL로 변환하고, 실행 결과를 반환한다. 단일 요청-응답 패턴.

### 2.2 요청

```json
{
    "question": "2024년 매출 성장률이 가장 높은 사업부는?",
    "datasource_id": "ds_business_main",
    "options": {
        "use_cache": true,
        "include_viz": true,
        "row_limit": 1000,
        "dialect": "postgres"
    }
}
```

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|------|----------|------|
| `question` | string | Yes | No | 자연어 질문 (최소 2자, 최대 2000자) |
| `datasource_id` | string | Yes | No | 대상 데이터소스 ID |
| `options` | object | No | Yes | 실행 옵션 |
| `options.use_cache` | boolean | No | - | 캐시된 쿼리 사용 여부 (기본: true) |
| `options.include_viz` | boolean | No | - | 시각화 추천 포함 여부 (기본: true) |
| `options.row_limit` | integer | No | - | 응답 행 수 제한 (기본: 1000, 최대: 10000) |
| `options.dialect` | string | No | - | SQL 방언 (기본: "postgres") |

### 2.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "question": "2024년 매출 성장률이 가장 높은 사업부는?",
        "sql": "SELECT d.dept_name, ROUND((SUM(CASE WHEN s.fiscal_year = 2024 THEN s.revenue ELSE 0 END) - SUM(CASE WHEN s.fiscal_year = 2023 THEN s.revenue ELSE 0 END)) / NULLIF(SUM(CASE WHEN s.fiscal_year = 2023 THEN s.revenue ELSE 0 END), 0) * 100, 2) AS growth_rate FROM sales_records s JOIN departments d ON s.dept_id = d.dept_id WHERE s.fiscal_year IN (2023, 2024) GROUP BY d.dept_name ORDER BY growth_rate DESC LIMIT 1000",
        "result": {
            "columns": [
                {"name": "dept_name", "type": "varchar"},
                {"name": "growth_rate", "type": "numeric"}
            ],
            "rows": [
                ["디지털사업부", 32.15]
            ],
            "row_count": 5,
            "truncated": false
        },
        "visualization": {
            "chart_type": "bar",
            "config": {
                "x_column": "dept_name",
                "y_column": "growth_rate",
                "x_label": "사업부",
                "y_label": "성장률(%)"
            }
        },
        "summary": "2024년 매출 성장률이 가장 높은 사업부는 디지털사업부(32.15%)입니다.",
        "metadata": {
            "execution_time_ms": 1247,
            "tables_used": ["sales_records", "departments"],
            "cache_hit": false,
            "guard_status": "FIX",
            "guard_fixes": ["LIMIT 1000 자동 추가"]
        }
    }
}
```

| 필드 | 타입 | Nullable | 설명 |
|------|------|----------|------|
| `success` | boolean | No | 요청 성공 여부 |
| `data.question` | string | No | 원본 질문 |
| `data.sql` | string | No | 생성/실행된 SQL |
| `data.result.columns` | array | No | 결과 컬럼 정보 |
| `data.result.rows` | array | No | 결과 행 데이터 |
| `data.result.row_count` | integer | No | 총 행 수 |
| `data.result.truncated` | boolean | No | 행 수 제한으로 잘렸는지 여부 |
| `data.visualization` | object | Yes | 시각화 추천 (include_viz=false이면 null) |
| `data.visualization.chart_type` | string | No | 차트 유형 (bar/line/pie/scatter/kpi_card/table) |
| `data.visualization.config` | object | No | 차트 설정 |
| `data.summary` | string | Yes | 결과 요약 (LLM 생성) |
| `data.metadata.execution_time_ms` | integer | No | 전체 실행 시간 (밀리초) |
| `data.metadata.tables_used` | array | No | 사용된 테이블 목록 |
| `data.metadata.cache_hit` | boolean | No | 캐시 히트 여부 |
| `data.metadata.guard_status` | string | No | SQL Guard 결과 (PASS/FIX) |
| `data.metadata.guard_fixes` | array | Yes | 적용된 자동 수정 목록 |

### 2.4 에러 응답

```json
{
    "success": false,
    "error": {
        "code": "SQL_GUARD_REJECT",
        "message": "생성된 SQL이 안전성 검증을 통과하지 못했습니다.",
        "details": {
            "violations": ["금지 키워드 발견: DELETE"],
            "suggestion": "데이터 조회(SELECT) 관련 질문으로 변경해주세요."
        }
    }
}
```

### 2.5 에러 코드

| 코드 | HTTP | 의미 | 사용자 메시지 |
|------|------|------|-------------|
| `QUESTION_TOO_SHORT` | 400 | 질문이 너무 짧음 | "2자 이상의 질문을 입력해주세요" |
| `QUESTION_TOO_LONG` | 400 | 질문이 너무 김 | "질문은 2000자 이내로 입력해주세요" |
| `DATASOURCE_NOT_FOUND` | 404 | 데이터소스 없음 | "지정된 데이터소스를 찾을 수 없습니다" |
| `SCHEMA_NOT_FOUND` | 404 | 관련 스키마 없음 | "질문과 관련된 테이블을 찾지 못했습니다" |
| `SQL_GENERATION_FAILED` | 500 | SQL 생성 실패 | "SQL 생성에 실패했습니다. 다시 시도해주세요" |
| `SQL_GUARD_REJECT` | 422 | SQL Guard 거부 | "생성된 SQL이 안전성 검증을 통과하지 못했습니다" |
| `SQL_EXECUTION_TIMEOUT` | 504 | SQL 실행 타임아웃 | "쿼리 실행 시간이 초과되었습니다 (30초)" |
| `SQL_EXECUTION_ERROR` | 500 | SQL 실행 에러 | "쿼리 실행 중 오류가 발생했습니다" |
| `LLM_UNAVAILABLE` | 503 | LLM 서비스 불가 | "AI 서비스에 일시적으로 연결할 수 없습니다" |
| `NEO4J_UNAVAILABLE` | 503 | Neo4j 불가 | "메타데이터 서비스에 연결할 수 없습니다" |

---

## 3. POST /text2sql/react

### 3.1 설명

ReAct(Reasoning + Acting) 패턴으로 다단계 추론을 수행한다. NDJSON(Newline-Delimited JSON) 스트림으로 각 단계의 중간 결과를 실시간 전송한다.

### 3.2 요청

```json
{
    "question": "작년 대비 프로세스 성공률이 가장 많이 변동한 조직 TOP 5는?",
    "datasource_id": "ds_business_main",
    "options": {
        "max_iterations": 5,
        "stream": true
    }
}
```

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|------|----------|------|
| `question` | string | Yes | No | 자연어 질문 |
| `datasource_id` | string | Yes | No | 대상 데이터소스 ID |
| `options.max_iterations` | integer | No | - | ReAct 최대 반복 횟수 (기본: 5, 최대: 10) |
| `options.stream` | boolean | No | - | 스트리밍 여부 (기본: true) |

### 3.3 응답 (200 OK, NDJSON Stream)

Content-Type: `application/x-ndjson`

각 줄은 독립적인 JSON 객체:

```
{"step": "select", "iteration": 1, "data": {"tables": ["process_metrics", "organizations", "process_outcomes"], "reasoning": "프로세스 성공률을 조직별로 비교하려면..."}}
{"step": "generate", "iteration": 1, "data": {"sql": "SELECT o.org_name, COUNT(CASE WHEN ...) ...", "reasoning": "2024년 조직별 성공률 계산..."}}
{"step": "validate", "iteration": 1, "data": {"status": "PASS", "sql": "SELECT ..."}}
{"step": "execute", "iteration": 1, "data": {"row_count": 15, "preview": [["본사", 0.72], ...]}}
{"step": "quality", "iteration": 1, "data": {"score": 0.85, "feedback": "2023년 데이터도 필요합니다"}}
{"step": "triage", "iteration": 1, "data": {"action": "continue", "reason": "비교 기준 연도 데이터 추가 필요"}}
{"step": "select", "iteration": 2, "data": {"tables": ["process_metrics_2023"], "reasoning": "2023년 데이터 조회..."}}
...
{"step": "result", "iteration": 3, "data": {"sql": "...", "result": {...}, "summary": "...", "visualization": {...}}}
```

**단계(step) 유형**:

| step | 설명 | data 내용 |
|------|------|----------|
| `select` | 테이블 선택 | tables, reasoning |
| `generate` | SQL 생성 | sql, reasoning |
| `validate` | SQL 검증 | status, sql, violations |
| `fix` | SQL 수정 (validate 실패 시) | original_sql, fixed_sql, fixes |
| `execute` | SQL 실행 | row_count, preview |
| `quality` | 품질 점검 | score, feedback |
| `triage` | 결과 분류/라우팅 | action (continue/complete/fail), reason |
| `result` | 최종 결과 | sql, result, summary, visualization |
| `error` | 에러 발생 | code, message |

### 3.4 에러 처리

스트림 중 에러 발생 시 에러 단계를 전송하고 스트림을 종료한다:

```
{"step": "error", "iteration": 3, "data": {"code": "MAX_ITERATIONS", "message": "최대 반복 횟수(5)에 도달했습니다."}}
```

---

## 4. POST /text2sql/direct-sql

### 4.1 설명

SQL을 직접 입력하여 실행한다. 관리자 전용 엔드포인트.

### 4.2 요청

```json
{
    "sql": "SELECT d.dept_name, COUNT(*) as cnt FROM sales_records s JOIN departments d ON s.dept_id = d.dept_id GROUP BY d.dept_name ORDER BY cnt DESC LIMIT 10",
    "datasource_id": "ds_business_main"
}
```

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|------|----------|------|
| `sql` | string | Yes | No | 실행할 SQL (SELECT만 허용) |
| `datasource_id` | string | Yes | No | 대상 데이터소스 ID |

### 4.3 응답 (200 OK)

```json
{
    "success": true,
    "data": {
        "result": {
            "columns": [
                {"name": "dept_name", "type": "varchar"},
                {"name": "cnt", "type": "bigint"}
            ],
            "rows": [
                ["디지털사업부", 1523],
                ["영업본부", 892]
            ],
            "row_count": 10,
            "truncated": false
        },
        "metadata": {
            "execution_time_ms": 234,
            "guard_status": "PASS"
        }
    }
}
```

### 4.4 권한

- **인증**: JWT 토큰 필수
- **역할**: Admin 이상 (일반 사용자는 `/ask` 사용)
- **감사**: 모든 직접 SQL 실행은 감사 로그에 기록

---

## 5. 공통 규칙

### 5.1 요청 헤더

| 헤더 | 값 | 필수 |
|------|-----|------|
| `Authorization` | `Bearer {jwt_token}` | Yes |
| `Content-Type` | `application/json` | Yes |
| `X-Datasource-Id` | 데이터소스 ID (대안) | No |

### 5.2 응답 형식 규칙

- 모든 응답은 `success` 필드를 포함한다
- 성공 시 `data` 객체에 결과가 담긴다
- 실패 시 `error` 객체에 에러 정보가 담긴다
- 날짜/시간은 ISO 8601 형식 (`2024-01-15T09:30:00Z`)
- 숫자는 JSON number 타입 (문자열 인코딩하지 않음)

### 5.3 Rate Limiting

| 엔드포인트 | 제한 | 단위 |
|-----------|------|------|
| `/ask` | 30 | 분당 요청 수 (사용자별) |
| `/react` | 10 | 분당 요청 수 (사용자별) |
| `/direct-sql` | 60 | 분당 요청 수 (사용자별) |

---

## 관련 문서

- [01_architecture/nl2sql-pipeline.md](../01_architecture/nl2sql-pipeline.md): NL2SQL 파이프라인 상세
- [02_api/meta-api.md](./meta-api.md): 메타데이터 API
- [02_api/feedback-api.md](./feedback-api.md): 피드백 API
- [07_security/sql-safety.md](../07_security/sql-safety.md): SQL 안전성 정책
