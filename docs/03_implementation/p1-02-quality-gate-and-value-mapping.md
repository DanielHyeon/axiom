# P1-02: 품질 게이트 활성화 + Value Mapping 구현 + 멀티턴 대화

> 갭 항목 #12 Quality Gate, #13 Value Mapping, #14 Multi-turn Context, #15 Query Vectorization
> 작성일: 2026-03-20
> 기준 소스: KAIR `robo-data-text2sql` (프로덕션 검증 완료)
> 대상 코드: Axiom `services/oracle/`

---

## 목차

1. [현재 상태 분석](#1-현재-상태-분석)
2. [KAIR 소스 분석](#2-kair-소스-분석)
3. [구현 항목 #12: 품질 게이트](#3-구현-항목-12-품질-게이트)
4. [구현 항목 #13: Value Mapping](#4-구현-항목-13-value-mapping)
5. [구현 항목 #14: 멀티턴 대화 컨텍스트](#5-구현-항목-14-멀티턴-대화-컨텍스트)
6. [구현 항목 #15: 쿼리 자동 벡터화 + 클러스터링](#6-구현-항목-15-쿼리-자동-벡터화--클러스터링)
7. [Neo4j 스키마 변경 사항](#7-neo4j-스키마-변경-사항)
8. [테스트 계획](#8-테스트-계획)
9. [보안 고려사항](#9-보안-고려사항)
10. [구현 순서 및 의존성](#10-구현-순서-및-의존성)

---

## 1. 현재 상태 분석

### 1.1 품질 게이트 스텁 (`cache_postprocess.py`)

**파일**: `services/oracle/app/pipelines/cache_postprocess.py`

```python
# 현재 코드 — confidence를 0.95 상수로 고정
class CachePostProcessor:
    async def quality_gate(self, question, sql, result_preview, datasource_id):
        confidence = 0.95  # <-- 항상 고정
        if confidence >= 0.90:
            return GateDecision(status="APPROVE", confidence=confidence)
```

**문제점**:
- LLM 심사 없이 모든 쿼리가 `APPROVE` (confidence=0.95)
- `result_preview` 파라미터를 전혀 사용하지 않음
- 잘못된 SQL이 Neo4j `:Query` 캐시로 영구 저장되어 후속 쿼리를 오염시킴
- 단일 라운드, 심사 근거(reasons/risk_flags) 없음

### 1.2 Value Mapping 스텁 (`value_mapping.py`)

**파일**: `services/oracle/app/core/value_mapping.py`

```python
# 현재 코드 — "성공" 키워드만 하드코딩
class ValueMappingExtractor:
    async def extract_value_mappings(self, question, sql):
        if "성공" in question or "SUCCESS" in sql:
            return [ValueMapping(natural_value="성공", db_value="SUCCESS", ...)]
        return []
```

**문제점**:
- 하드코딩된 1건의 매핑만 존재 (`"성공" -> "SUCCESS"`)
- Neo4j `:ValueMapping` 노드 참조 없음 (그래프 검색 미활용)
- DB probe 없음 (실제 컬럼 값 확인 불가)
- SQL WHERE 절의 리터럴과 실제 DB 값 불일치 감지 불가

### 1.3 멀티턴 대화 (미구현)

**현재 상태**:
- `AskRequest`/`ReactRequest`에 `conversation_token` 필드 없음
- 매 요청이 독립적 (이전 대화 컨텍스트 완전 소실)
- 후속 질문 ("방금 결과에서 서울만 필터해줘") 처리 불가

### 1.4 쿼리 벡터화 (미구현)

**현재 상태**:
- `query_history_repo.save_query_history()`는 PostgreSQL에 단순 저장
- Neo4j `:Query` 노드 생성 없음 (KAIR는 있음)
- 유사 쿼리 벡터 검색 인프라 부재

### 1.5 React Agent 루프 내 품질 판단

**파일**: `services/oracle/app/pipelines/react_agent.py`

```python
# 현재: MockLLMClient가 항상 score=0.85 반환
async def run_step_quality(self, question, sql):
    prompt = f"Assess quality of: {question} \nSQL: {sql}"
    res = await llm_factory.generate(prompt, system_prompt="당신은 SQL 결과 품질 심사관입니다.")
    return json.loads(res)  # MockLLMClient → {"score": 0.85, "is_complete": true}
```

**문제점**:
- Mock LLM이 항상 동일한 점수 반환
- 실제 LLM 프롬프트 구조 없음 (구조화된 JSON 스키마 미정의)
- Rubric 기반 요구사항 추출 + 체크 로직 없음

---

## 2. KAIR 소스 분석

### 2.1 품질 게이트 알고리즘 (KAIR `query_quality_gate_generator.py`)

KAIR의 품질 게이트는 **LLM 기반 N-라운드 심사** 구조:

**핵심 구조**:
```
QueryQualityGateGenerator
  ├── 시스템 프롬프트: query_quality_gate_prompt.md
  ├── LLM: light 모델 (비용/지연 최소화), temperature=0.0, max_tokens=700
  └── judge_round(question, sql, row_count, execution_time_ms, metadata, steps_tail, preview, round_idx)
       └── 출력: QueryQualityJudgeResult(accept, confidence, reasons, risk_flags, summary)
```

**프롬프트 핵심 원칙** (`query_quality_gate_prompt.md`):
1. **Fail-closed**: 애매하면 반드시 거절 (잘못된 캐시가 후속 쿼리 오염)
2. 질문 의도 부합성 평가 (대상/기간/집계/단위/필터/조인 의미)
3. preview(rows/columns) → 강한 근거로 사용
4. metadata/steps_tail → 참고 신호 (SQL/preview와 충돌 시 보수적 판단)

**출력 JSON 스키마** (추가 키 금지 — Pydantic `extra="forbid"`):
```json
{
  "accept": true|false,
  "confidence": 0.0~1.0,
  "reasons": ["짧은 근거"],
  "risk_flags": ["리스크 키워드"],
  "summary": "한줄 요약"
}
```

**안전장치**:
- Pydantic `ConfigDict(extra="forbid")` → 예상치 못한 키 포함 시 파싱 실패
- 파싱 실패 → `accept=False, confidence=0.0` (fail-closed)
- LLM 호출 실패 → `accept=False, confidence=0.0` (fail-closed)
- `_clamp01()` → confidence 범위 강제

### 2.2 Rubric Judge (KAIR `rubric_judge.py` + `controller.py`)

KAIR의 Controller는 품질 게이트와 별개로 **Rubric 기반 요구사항 추출 + 후보 평가** 구조를 가짐:

```
controller.py::run_controller()
  ├── Phase 0: extract_requirements(llm, question) → List[RubricRequirement]
  │     - 각 요구사항: id, must(필수여부), type(집계/필터/조인/기간...), text
  ├── Phase 1: Explore (N개 SQL 후보 생성 + 각각 validate_sql + rubric 평가)
  │     - evaluate_candidate(llm, question, sql, preview, context_evidence, requirements)
  │     → List[RubricCheck(id, status=PASS|FAIL|UNKNOWN, why)]
  │     - compute_score_and_accept(requirements, checks)
  │     → (score, accept, missing_must, fail_must_ids)
  │     - accept = True only when 모든 MUST 요구사항 PASS
  ├── Phase 2: Converge (repair loop — failed checks를 근거로 SQL 수정)
  │     - get_controller_repair_generator().generate(failed_checks, passed_must_ids, ...)
  │     - stall 감지: 동일 SQL 반복 or 동일 fail_ids → stall++
  └── Phase 3: Escape (stall 시 2nd best 후보로 전환, 1회 허용)
```

**Axiom 적용 방안**:
- Rubric Judge 전체를 이식하는 것은 Phase 2 범위 (현재 Axiom의 react_agent 구조를 크게 변경해야 함)
- **Phase 1 (현재 구현 범위)**: 품질 게이트(`query_quality_gate_generator` 패턴)만 이식
- 이후 Rubric Judge는 react_agent 리팩토링 시 통합

### 2.3 Value Mapping 추출/검증 (KAIR)

KAIR의 Value Mapping은 **3계층 파이프라인**:

**계층 1: Neo4j `:ValueMapping` 노드 (사전 등록/학습된 매핑)**
```cypher
(:ValueMapping {natural_value, code_value, column_fqn, usage_count, verified, verified_confidence})
    └──[:MAPS_TO]──► (:Column {fqn})
```
- `save_value_mapping_by_fqn()`: Column.fqn 기반 MERGE (중복 방지)
- `find_value_mapping(natural_value)`: CONTAINS 검색 + usage_count DESC 정렬
- `verified` 플래그: 품질 게이트 통과 시 `verified=True` 마킹

**계층 2: `resolved_values_flow.py` — 실시간 값 해석**
```
resolve_values_and_append_xml()
  ├── Priority 1: ValueMapping 노드에서 매핑 조회
  │     - natural_value → code_value 직접 대입
  └── Priority 2: limited DB probe (strict budget)
       - 제한: probe_budget=2회, timeout=2초, value_limit=10건
       - text-ish 컬럼 선택 → ILIKE '%keyword%' 실행 → 매칭 값 반환
```

**계층 3: `column_value_hints_flow.py` — 컬럼별 enum 값 힌트**
- Neo4j Column 노드의 `enum_values` (JSON 문자열)에서 파싱
- 한국어 확장 검색: 조사 제거 (`청주정수장의` → `청주정수장`), 행정구역 접미사 제거
- `_pick_values_with_query_match()`: 검색어와 매칭되는 값 우선 포함

**Axiom 적용 방안**:
- 계층 1 (Neo4j ValueMapping) → `save_value_mapping_by_fqn` 패턴을 Synapse ACL 통해 이식
- 계층 2 (DB probe) → `sql_executor`를 활용한 제한적 값 조회 구현
- 계층 3 (enum hints) → Synapse의 `search_schema_context` 응답에 포함시킴

### 2.4 ConversationCapsule (KAIR)

KAIR의 멀티턴 대화 상태는 **클라이언트 저장 토큰** 방식:

```
ConversationCapsule
  ├── v: int (버전)
  ├── dbms: str
  ├── schema_filter: List[str]
  ├── turns: List[TurnCapsule]  (최대 40턴)
  │     └── TurnCapsule
  │           ├── question: str
  │           ├── final_sql: str
  │           ├── preview: TurnPreview (columns, rows[:5], row_count, execution_time_ms)
  │           ├── derived_filters: Dict[str,str]  (SQL WHERE에서 추출한 등호 필터)
  │           ├── important_hints: Dict[str,Any]  (메타데이터 XML에서 추출한 힌트)
  │           └── evidence_ctx_xml: str  (build_sql_context 결과 필터링)
  ├── created_at_ms: int
  └── updated_at_ms: int
```

**직렬화**: `JSON → zlib(level=6) → base64url` (10+ 턴에서도 컴팩트)

**컨텍스트 선택 알고리즘** (`build_conversation_context`):
1. 최근 N턴 (기본 5) 무조건 포함
2. 나머지에서 Jaccard 유사도 기반 M턴 (기본 3) 선택
3. 중복 SQL 제거 (동일 SQL → 최신 인덱스만 유지)
4. 미리보기 축소 (max_cols=12, max_rows=3)

**보안 경고**: KAIR 토큰은 **비서명** (주석에 명시: "NOT signed, tamperable, intentional per current policy")

### 2.5 :Query 노드 스키마 (KAIR `neo4j_history.py`)

```cypher
(:Query {
  id,                      -- MD5(db + question)[:12]
  question, question_norm,
  sql, status,
  row_count, execution_time_ms, steps_count,
  error_message, steps_summary,
  created_at, created_at_ms,
  last_seen_at, last_seen_at_ms, seen_count,
  updated_at, updated_at_ms, best_run_at_ms,
  tables_used, columns_used,
  value_mappings_count, value_mapping_terms,
  -- Verification (quality gate)
  verified, verified_confidence, verified_confidence_avg,
  verified_source, verified_at, verified_at_ms,
  quality_gate_json,
  -- Best context (overwrite policy 분리)
  best_context_score, best_context_steps_features,
  best_context_steps_summary, best_context_run_at_ms,
  -- Vector indexes
  vector_question,         -- 질문 벡터 (cosine 유사도)
  vector_intent            -- 의도 벡터 (cosine 유사도)
})
```

**관계**:
```
(:Query)-[:USES_TABLE]→(:Table)
(:Query)-[:SELECTS]→(:Column)
(:Query)-[:FILTERS {op, value}]→(:Column)
(:Query)-[:AGGREGATES {fn}]→(:Column)
(:Query)-[:JOINS_ON]→(:Column)
(:Query)-[:GROUPS_BY]→(:Column)
```

**Overwrite 정책**: `completed > steps_count(min) > execution_time_ms(min) > best_run_at_ms(latest)`

---

## 3. 구현 항목 #12: 품질 게이트

### 3.1 아키텍처 개요

```
NL2SQL Pipeline / React Agent
       │
       ▼
CachePostProcessor.quality_gate()
       │
       ├── Round 1: LLM Judge 호출
       │     - 입력: question, sql, preview, metadata
       │     - 출력: QualityJudgeResult(accept, confidence, reasons, risk_flags, summary)
       │
       ├── (Optional) Round 2: confidence가 중간 구간일 때 재심사
       │     - 추가 신호 주입 (semantic mismatch, preview stats)
       │
       └── 최종 결정
             - APPROVE: accept=True AND avg_confidence >= 0.80
             - PENDING: accept=True AND avg_confidence >= 0.60
             - REJECT: accept=False OR avg_confidence < 0.60
```

### 3.2 새 파일: `services/oracle/app/core/quality_judge.py`

**목적**: LLM 기반 품질 심사 로직 (cache_postprocess와 분리)

```python
# 구현 사양
class QualityJudgeLLMOutput(BaseModel):
    """LLM 출력 스키마 (추가 키 금지)"""
    model_config = ConfigDict(extra="forbid")
    accept: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    summary: str = ""

@dataclass
class QualityJudgeResult:
    accept: bool
    confidence: float
    reasons: list[str]
    risk_flags: list[str]
    summary: str
    parse_error: str = ""

class QualityJudge:
    SYSTEM_PROMPT: str  # 아래 3.3에서 정의

    async def judge_round(
        self,
        question: str,
        sql: str,
        row_count: int | None,
        execution_time_ms: float | None,
        preview: dict | None,       # {columns, rows, row_count}
        metadata: dict | None,      # 추출된 테이블/컬럼 힌트
        round_idx: int = 0,
    ) -> QualityJudgeResult:
        """단일 라운드 LLM 심사"""
        ...

    async def multi_round_judge(
        self,
        question: str,
        sql: str,
        row_count: int | None,
        execution_time_ms: float | None,
        preview: dict | None,
        metadata: dict | None,
        max_rounds: int = 2,
    ) -> QualityJudgeResult:
        """N-라운드 심사. Round 1 결과에 따라 Round 2 실행 여부 결정"""
        ...
```

**N-라운드 로직**:
1. **Round 1**: 기본 심사 (question, sql, preview)
2. **Round 2 조건**: Round 1의 confidence가 0.55~0.85 구간 (애매한 영역)
   - Round 2에서는 추가 신호 주입:
     - `semantic_mismatch_reasons(question, sql)` — 집계/기간 불일치 감지
     - `preview_non_null_stats(preview)` — NULL 셀 비율
   - Round 2 결과와 Round 1 결과의 가중 평균 계산
3. **최종 판정**:
   - `avg_confidence >= 0.80 AND 모든 라운드 accept=True` → APPROVE
   - `avg_confidence >= 0.60 AND 최소 1라운드 accept=True` → PENDING
   - 그 외 → REJECT

### 3.3 프롬프트 설계

**파일**: `services/oracle/app/prompts/quality_gate_prompt.md`

```markdown
당신은 Text2SQL 결과를 캐시로 저장해도 되는지 엄격히 판정하는 심사자입니다.
반드시 **단 하나의 JSON 객체만** 출력하세요. (설명문/마크다운/코드펜스 금지)

핵심 원칙:
- Fail-closed: 애매하면 반드시 거절(accept=false)하세요.
  잘못 저장된 캐시는 이후 질의를 오염시킵니다.
- 질문 의도 부합성 평가:
  1. 대상(엔티티/테이블) 일치 여부
  2. 기간/날짜 필터 일치 여부
  3. 집계 함수(AVG/SUM/COUNT 등) 일치 여부
  4. GROUP BY/정렬 기준 일치 여부
  5. WHERE 조건의 값이 실제 DB 값과 일치하는지
- preview(rows/columns)가 주어지면 그것을 강한 근거로 사용하세요.
  - row_count=0이면 거절
  - 모든 셀이 NULL이면 거절
  - 컬럼이 질문의 요청과 무관하면 거절
- round_idx > 0 이면 이전 라운드 피드백을 참고하되, 독립적으로 재판단하세요.

입력(JSON):
- question: 사용자 질문
- sql: 최종 SQL
- signals:
  - row_count, execution_time_ms, preview: {columns, rows, row_count}
  - semantic_mismatches: ["missing AVG()", ...] (있으면)
  - null_ratio: float (있으면, 0.0~1.0)
- round_idx: 현재 심사 라운드 (0-based)

출력(JSON 스키마; **추가 키 금지**):
{
  "accept": true|false,
  "confidence": 0.0~1.0,
  "reasons": ["짧은 근거"],
  "risk_flags": ["리스크 키워드"],
  "summary": "한줄 요약"
}
```

### 3.4 `cache_postprocess.py` 변경

```python
# 변경 후 구조
class CachePostProcessor:
    def __init__(self):
        self._judge = QualityJudge()  # 새 의존성

    async def quality_gate(
        self,
        question: str,
        sql: str,
        result_preview: list,
        datasource_id: str,
        *,
        execution_time_ms: float | None = None,
        metadata: dict | None = None,
    ) -> GateDecision:
        # preview를 {columns, rows, row_count} 형태로 변환
        preview = self._format_preview(result_preview)

        # LLM N-라운드 심사
        judge_result = await self._judge.multi_round_judge(
            question=question,
            sql=sql,
            row_count=preview.get("row_count"),
            execution_time_ms=execution_time_ms,
            preview=preview,
            metadata=metadata,
            max_rounds=2,
        )

        # 판정 변환
        if judge_result.accept and judge_result.confidence >= 0.80:
            status = "APPROVE"
        elif judge_result.accept and judge_result.confidence >= 0.60:
            status = "PENDING"
        else:
            status = "REJECT"

        return GateDecision(
            status=status,
            confidence=judge_result.confidence,
            reasons=judge_result.reasons,      # 새 필드
            risk_flags=judge_result.risk_flags, # 새 필드
        )

    async def process(self, ...):
        decision = await self.quality_gate(...)
        if decision.status == "APPROVE":
            await self.persist_query(
                ...,
                verified=True,
                verified_confidence=decision.confidence,
                quality_gate_json=decision.model_dump_json(),
            )
        elif decision.status == "PENDING":
            # PENDING: 저장하되 verified=False 마킹 (수동 검토 대기)
            await self.persist_query(
                ...,
                verified=False,
                verified_confidence=decision.confidence,
                quality_gate_json=decision.model_dump_json(),
            )
        # REJECT: 저장하지 않음
```

### 3.5 GateDecision 모델 확장

```python
class GateDecision(BaseModel):
    status: str                    # APPROVE | PENDING | REJECT
    confidence: float
    reasons: list[str] = []        # 신규: 판정 근거
    risk_flags: list[str] = []     # 신규: 위험 신호
    summary: str = ""              # 신규: 한줄 요약
```

### 3.6 React Agent 통합

`react_agent.py`의 `run_step_quality()`를 `QualityJudge`로 교체:

```python
class ReactAgent:
    def __init__(self):
        self._quality_judge = QualityJudge()

    async def run_step_quality(self, question: str, sql: str, preview: dict | None = None) -> dict:
        result = await self._quality_judge.judge_round(
            question=question,
            sql=sql,
            row_count=preview.get("row_count") if preview else None,
            execution_time_ms=None,
            preview=preview,
            metadata=None,
            round_idx=0,
        )
        return {
            "score": result.confidence,
            "is_complete": result.accept,
            "feedback": result.summary,
            "reasons": result.reasons,
            "risk_flags": result.risk_flags,
        }
```

### 3.7 LLM 호출 구현 세부사항

**LLM 선택**:
- `llm_factory.generate()`를 사용 (현재 MockLLMClient → 실 LLM 전환 시 동작)
- temperature=0.0 (결정론적 판단)
- max_tokens=700 (JSON 출력이므로 짧음)
- system_prompt에 quality_gate_prompt.md 내용 주입

**파싱 안전장치**:
1. 코드 펜스 제거 (```` ```json ... ``` ```` → JSON 추출)
2. `_extract_first_json_object()`: `{` ~ `}` 범위 추출
3. Pydantic `model_validate()` + `extra="forbid"`
4. 실패 시 fail-closed: `accept=False, confidence=0.0`

**semantic_mismatch_reasons 구현** (KAIR `controller.py` 이식):
```python
def semantic_mismatch_reasons(question: str, sql: str) -> list[str]:
    reasons = []
    uq, s = question.lower(), sql.lower()
    if any(k in uq for k in ("평균", "average", "avg")) and "avg(" not in s:
        reasons.append("missing AVG()")
    if any(k in uq for k in ("합계", "총합", "sum")) and "sum(" not in s:
        reasons.append("missing SUM()")
    # ... COUNT, MAX, MIN, GROUP BY 동일 패턴
    return reasons
```

### 3.8 실패 시 후처리

**품질 게이트 REJECT 시**:
- `cache_postprocess.process()`: Neo4j 저장 건너뜀
- React Agent: `triage.action = "CONTINUE"` (재시도) 또는 `"FAIL"` (거부)
- 로그에 `reasons` + `risk_flags` 기록 (디버깅용)

**품질 게이트 PENDING 시**:
- Neo4j에 `verified=False`로 저장
- 향후 관리자 UI에서 수동 검토/승인 기능 연동 가능
- 유사 쿼리 검색에서 `verified=True` 쿼리 우선 반환

---

## 4. 구현 항목 #13: Value Mapping

### 4.1 아키텍처 개요

```
사용자 질문: "서울 지역의 매출 합계"
       │
       ▼
ValueMappingService
  ├── 1단계: Neo4j :ValueMapping 노드 조회 (사전 학습된 매핑)
  │     - "서울" → region='서울' (usage_count=47, verified=true)
  │
  ├── 2단계: DB Probe (제한적 실 DB 조회)
  │     - 매핑 미발견 용어 → 텍스트 컬럼 ILIKE 검색
  │     - budget=2회, timeout=2초, limit=10건
  │
  └── 3단계: SQL 리터럴 검증
        - 생성된 SQL의 WHERE col='val' → val이 실제 DB 값인지 확인
        - value_hints(enum_values)와 대조
```

### 4.2 새 파일: `services/oracle/app/core/value_mapping_service.py`

기존 `value_mapping.py`는 모델만 남기고, 서비스 로직은 새 파일로 분리:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ResolvedValue:
    user_term: str
    actual_value: str
    source: str         # "neo4j_mapping" | "db_probe" | "enum_hint"
    column_fqn: str
    confidence: float   # 1.0 for neo4j verified, 0.7~0.9 for db_probe

class ValueMappingService:
    """자연어 → DB 값 매핑 서비스"""

    async def resolve_values(
        self,
        question: str,
        datasource_id: str,
        tenant_id: str,
        *,
        search_terms: list[str] | None = None,
    ) -> list[ResolvedValue]:
        """3단계 값 해석 파이프라인"""
        resolved: list[ResolvedValue] = []
        resolved_terms: set[str] = set()

        # 1단계: Neo4j ValueMapping 조회 (Synapse ACL 경유)
        terms = search_terms or self._extract_search_terms(question)
        for term in terms:
            mappings = await self._lookup_neo4j_mappings(term, tenant_id)
            for m in mappings:
                if m.natural_value.lower() not in resolved_terms:
                    resolved.append(ResolvedValue(
                        user_term=m.natural_value,
                        actual_value=m.db_value,
                        source="neo4j_mapping",
                        column_fqn=m.column_fqn,
                        confidence=1.0 if m.verified else 0.8,
                    ))
                    resolved_terms.add(m.natural_value.lower())

        # 2단계: DB Probe (미해석 용어만)
        unresolved = [t for t in terms if t.lower() not in resolved_terms]
        for term in unresolved[:2]:  # budget=2
            probed = await self._db_probe(term, datasource_id, tenant_id)
            if probed:
                resolved.append(probed)
                resolved_terms.add(term.lower())

        return resolved

    async def validate_sql_literals(
        self,
        sql: str,
        value_hints: dict[str, set[str]],  # column_name_lower → {allowed_values_lower}
    ) -> list[dict]:
        """SQL WHERE 절의 리터럴이 실제 DB 값인지 검증"""
        mismatches = []
        for col, val in self._extract_equality_filters(sql):
            allowed = value_hints.get(col.lower())
            if allowed and val.lower() not in allowed:
                mismatches.append({"column": col, "value": val, "allowed_sample": list(allowed)[:5]})
        return mismatches

    async def save_learned_mapping(
        self,
        natural_value: str,
        code_value: str,
        column_fqn: str,
        verified: bool = False,
        confidence: float | None = None,
    ) -> None:
        """품질 게이트 통과 후 학습된 매핑을 Neo4j에 저장"""
        await oracle_synapse_acl.save_value_mapping(
            natural_value=natural_value,
            code_value=code_value,
            column_fqn=column_fqn,
            verified=verified,
            verified_confidence=confidence,
        )

    def _extract_search_terms(self, question: str) -> list[str]:
        """질문에서 검색 용어 추출 (한국어 조사 제거 포함)"""
        ...

    def _extract_equality_filters(self, sql: str) -> list[tuple[str, str]]:
        """SQL에서 col='value' 패턴 추출"""
        ...

    async def _lookup_neo4j_mappings(self, term: str, tenant_id: str) -> list:
        """Synapse ACL → Neo4j ValueMapping 노드 검색"""
        ...

    async def _db_probe(self, term: str, datasource_id: str, tenant_id: str) -> ResolvedValue | None:
        """제한적 DB 조회로 값 탐색"""
        ...
```

### 4.3 기존 `value_mapping.py` 역할 변경

**Before**: 전체 로직 (스텁)
**After**: Pydantic 모델만 보관 (데이터 전송 객체)

```python
# value_mapping.py — 모델만 유지
class ValueMapping(BaseModel):
    natural_value: str
    db_value: str
    column_fqn: str
    confidence: float = 1.0
    verified: bool = False
    source: str = ""  # 신규: "neo4j_mapping" | "db_probe" | "manual"
```

### 4.4 DB Probe 구현 세부사항

KAIR의 `_limited_db_probe()` 패턴 적용:

```python
async def _db_probe(self, term: str, datasource_id: str, tenant_id: str) -> ResolvedValue | None:
    """
    제한적 DB 조회: text-ish 컬럼에서 keyword ILIKE 검색
    - timeout: 2초
    - limit: 10건
    - 결과 중 첫 번째 값 반환
    """
    # 1. 스키마에서 text-ish 컬럼 목록 조회
    tables = await oracle_synapse_acl.list_tables(tenant_id=tenant_id)
    for table in tables[:5]:  # 테이블 5개까지만 탐색
        detail = await oracle_synapse_acl.get_table_detail(tenant_id=tenant_id, table_name=table.name)
        for col in (detail.columns if detail else []):
            if col.data_type.lower() in ("varchar", "text", "character varying", ""):
                # 제한적 ILIKE 쿼리
                probe_sql = f"SELECT DISTINCT \"{col.name}\" FROM \"{table.name}\" WHERE \"{col.name}\" ILIKE '%{term}%' LIMIT 10"
                try:
                    result = await sql_executor.execute_sql(
                        probe_sql, datasource_id, timeout_seconds=2.0
                    )
                    if result.rows:
                        return ResolvedValue(
                            user_term=term,
                            actual_value=str(result.rows[0][0]),
                            source="db_probe",
                            column_fqn=f"{table.name}.{col.name}",
                            confidence=0.75,
                        )
                except Exception:
                    continue
    return None
```

**보안 주의**: DB probe SQL은 **읽기 전용 SELECT** + `sql_guard` 통과 필수.

### 4.5 NL2SQL Pipeline 통합

`nl2sql_pipeline.py`의 `execute()` 메서드에 Value Mapping 서비스 통합:

```python
# 변경: step 2와 step 4 사이에 삽입
class NL2SQLPipeline:
    def __init__(self):
        self._value_mapping_svc = ValueMappingService()  # 신규

    async def execute(self, question, datasource_id, options, user, case_id=None):
        ...
        # 2. Graph search + schema catalog (기존)
        schema_catalog, schema_source, value_mappings, similar_queries, ontology_ctx = ...

        # 2.5 Value Mapping 활성화 (신규)
        resolved_values = await self._value_mapping_svc.resolve_values(
            question=question,
            datasource_id=datasource_id,
            tenant_id=tenant_id,
        )
        # resolved_values를 value_mappings에 병합
        for rv in resolved_values:
            value_mappings.append({
                "natural_language": rv.user_term,
                "db_value": rv.actual_value,
                "column": rv.column_fqn.split(".")[-1] if rv.column_fqn else "",
                "table": rv.column_fqn.split(".")[-2] if "." in rv.column_fqn else "",
            })

        # 4. LLM SQL generation (기존 — value_mappings 이제 실제 데이터)
        generated_sql = await self._generate_sql_llm(
            question, schema_catalog, value_mappings, similar_queries, row_limit, dialect,
            ontology_ctx=ontology_ctx,
        )

        # 4.5 SQL 리터럴 검증 (신규)
        mismatches = await self._value_mapping_svc.validate_sql_literals(
            generated_sql, value_hints=self._build_value_hints(schema_catalog)
        )
        if mismatches:
            logger.warning("sql_literal_mismatch", mismatches=mismatches)
            # 향후: 자동 수정 또는 사용자 확인 요청

        ...

        # 9. Cache/quality gate 후 학습 (신규)
        # 품질 게이트 APPROVE 시 → 추출된 매핑을 Neo4j에 저장
        if decision.status == "APPROVE":
            for rv in resolved_values:
                await self._value_mapping_svc.save_learned_mapping(
                    natural_value=rv.user_term,
                    code_value=rv.actual_value,
                    column_fqn=rv.column_fqn,
                    verified=True,
                    confidence=decision.confidence,
                )
```

### 4.6 한국어 검색어 확장

KAIR의 `_expand_search_terms()` 패턴 이식:

```python
_KOREAN_PARTICLES = ("의", "을", "를", "은", "는", "이", "가", "과", "와", "에", "에서", "으로", "로")
_KOREAN_ADMIN_SUFFIXES = ("시", "군", "구", "도", "읍", "면", "동")

def expand_search_terms(terms: list[str]) -> list[str]:
    """한국어 조사/접미사 제거로 검색 범위 확장"""
    expanded = []
    seen = set()
    for term in terms:
        candidates = [term]
        for suf in _KOREAN_PARTICLES + _KOREAN_ADMIN_SUFFIXES:
            if term.endswith(suf) and len(term) >= 3:
                candidates.append(term[:-len(suf)])
        for c in candidates:
            c = c.strip()
            if len(c) >= 2 and c.lower() not in seen:
                seen.add(c.lower())
                expanded.append(c)
    return expanded[:20]
```

---

## 5. 구현 항목 #14: 멀티턴 대화 컨텍스트

### 5.1 설계 원칙

KAIR 방식 (클라이언트 토큰, 비서명) vs Axiom 요구사항 (JWT 보안 체계):

| 항목 | KAIR | Axiom (구현안) |
|------|------|----------------|
| 저장 위치 | 클라이언트 토큰 | **서버 사이드 (Redis)** |
| 직렬화 | zlib + base64url | JSON (Redis 내장 직렬화) |
| 서명 | 없음 (비서명) | **세션 키 = JWT sub + 타임스탬프** |
| TTL | 없음 (영구) | **30분 (Redis TTL)** |
| 상한 | 40턴 | 20턴 (Axiom은 단일 세션 범위) |

**핵심 결정**: 서버 사이드 Redis 저장을 선택하는 이유:
1. Axiom은 JWT 기반 인증 — 클라이언트 토큰 변조 방지가 필수
2. Redis에 이미 의존 (캐시, rate limiting)
3. 토큰 크기 제한 없음 (HTTP 헤더 4KB 제약 회피)

### 5.2 새 파일: `services/oracle/app/core/conversation_state.py`

```python
import json
import time
from dataclasses import dataclass, field
from typing import Any

@dataclass
class TurnState:
    question: str
    final_sql: str
    preview_columns: list[str] = field(default_factory=list)
    preview_rows: list[list] = field(default_factory=list)
    row_count: int = 0
    derived_filters: dict[str, str] = field(default_factory=dict)
    created_at_ms: int = 0

@dataclass
class ConversationState:
    session_id: str
    user_id: str
    datasource_id: str
    turns: list[TurnState] = field(default_factory=list)
    created_at_ms: int = 0
    updated_at_ms: int = 0

    MAX_TURNS: int = 20

    def append_turn(self, turn: TurnState) -> None:
        self.turns.append(turn)
        if len(self.turns) > self.MAX_TURNS:
            self.turns = self.turns[-self.MAX_TURNS:]
        self.updated_at_ms = int(time.time() * 1000)

    def build_context_for_followup(self, followup_question: str) -> dict:
        """KAIR build_conversation_context 알고리즘 적용"""
        # 최근 5턴 + Jaccard 유사도 상위 3턴 선택
        ...

    def to_dict(self) -> dict:
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationState":
        ...
```

### 5.3 새 파일: `services/oracle/app/core/conversation_store.py`

```python
import json
from app.core.config import settings

class ConversationStore:
    """Redis 기반 대화 상태 저장소"""

    REDIS_PREFIX = "nl2sql:conversation:"
    TTL_SECONDS = 1800  # 30분

    def _key(self, session_id: str) -> str:
        return f"{self.REDIS_PREFIX}{session_id}"

    async def get(self, session_id: str) -> ConversationState | None:
        ...

    async def save(self, state: ConversationState) -> None:
        ...

    async def delete(self, session_id: str) -> None:
        ...

    def generate_session_id(self, user_id: str, datasource_id: str) -> str:
        """user_id + datasource_id + timestamp 기반 세션 ID 생성"""
        ...
```

### 5.4 API 변경

```python
# text2sql.py — AskRequest / ReactRequest 확장
class AskRequest(BaseModel):
    question: str
    datasource_id: str
    case_id: str | None = None
    session_id: str | None = None  # 신규: 멀티턴 세션 ID
    options: AskOptions = Field(default_factory=AskOptions)

class ReactRequest(BaseModel):
    question: str
    datasource_id: str
    case_id: str | None = None
    session_id: str | None = None  # 신규: 멀티턴 세션 ID
    options: ReactOptions = Field(default_factory=ReactOptions)
```

**응답에 session_id 포함**:
```python
# ask_question 응답
return {
    "success": True,
    "data": {
        ...
        "metadata": {
            ...,
            "session_id": session_id,  # 클라이언트가 후속 요청에 재사용
        }
    }
}
```

### 5.5 Pipeline 통합

```python
class NL2SQLPipeline:
    async def execute(self, question, datasource_id, options, user, case_id=None, session_id=None):
        ...
        # 0. 대화 컨텍스트 로드 (신규)
        conversation_ctx = None
        if session_id:
            state = await conversation_store.get(session_id)
            if state and state.user_id == user.user_id:  # 소유자 검증
                conversation_ctx = state.build_context_for_followup(question)

        # 4. LLM SQL generation — conversation context 주입
        generated_sql = await self._generate_sql_llm(
            question, schema_catalog, value_mappings, similar_queries, row_limit, dialect,
            ontology_ctx=ontology_ctx,
            conversation_context=conversation_ctx,  # 신규
        )

        ...

        # 11. 대화 상태 업데이트 (신규)
        if session_id is None:
            session_id = conversation_store.generate_session_id(user.user_id, datasource_id)
        state = await conversation_store.get(session_id) or ConversationState(
            session_id=session_id,
            user_id=user.user_id,
            datasource_id=datasource_id,
        )
        state.append_turn(TurnState(
            question=question,
            final_sql=guard_res.sql,
            preview_columns=exec_res.columns[:12],
            preview_rows=(exec_res.rows or [])[:5],
            row_count=exec_res.row_count,
            derived_filters=self._extract_filters(guard_res.sql),
        ))
        await conversation_store.save(state)
```

### 5.6 대화 컨텍스트 프롬프트 주입

`_format_schema_ddl()` 또는 별도 섹션으로 LLM에 이전 대화 주입:

```python
def _format_conversation_context(self, ctx: dict | None) -> str:
    if not ctx or not ctx.get("turns"):
        return ""
    lines = ["\n## Previous conversation turns (reference for follow-up):"]
    for t in ctx["turns"][-5:]:
        lines.append(f"- Q: {t['question']}")
        lines.append(f"  SQL: {t['final_sql'][:200]}")
        if t.get("derived_filters"):
            lines.append(f"  Filters: {t['derived_filters']}")
        if t.get("preview", {}).get("row_count"):
            lines.append(f"  Result: {t['preview']['row_count']} rows")
    return "\n".join(lines)
```

---

## 6. 구현 항목 #15: 쿼리 자동 벡터화 + 클러스터링

### 6.1 :Query 노드 저장 파이프라인

품질 게이트 APPROVE 시 Neo4j에 :Query 노드 생성:

```python
# cache_postprocess.py — persist_query 확장
async def persist_query(self, question, sql, confidence, datasource_id, tenant_id=None):
    # 1. 기존: Synapse ACL 경유 캐시 반영
    await oracle_synapse_acl.reflect_cache(question, sql, confidence, datasource_id)

    # 2. 신규: 질문 벡터 생성
    question_vector = await llm_factory.embed(question)

    # 3. 신규: Neo4j :Query 노드 저장 (Synapse ACL 경유)
    await oracle_synapse_acl.save_query_node(
        question=question,
        sql=sql,
        datasource_id=datasource_id,
        tenant_id=tenant_id,
        confidence=confidence,
        question_vector=question_vector,
        verified=True,
    )
```

### 6.2 Synapse ACL 확장

`synapse_acl.py`에 새 메서드 추가:

```python
class OracleSynapseACL:
    async def save_query_node(
        self,
        question: str,
        sql: str,
        datasource_id: str,
        tenant_id: str | None,
        confidence: float,
        question_vector: list[float],
        verified: bool = False,
    ) -> str:
        """Neo4j :Query 노드 MERGE (Synapse 경유)"""
        ...

    async def save_value_mapping(
        self,
        natural_value: str,
        code_value: str,
        column_fqn: str,
        verified: bool = False,
        verified_confidence: float | None = None,
    ) -> None:
        """Neo4j :ValueMapping 노드 MERGE (Synapse 경유)"""
        ...

    async def find_value_mappings(
        self,
        term: str,
        tenant_id: str,
    ) -> list[ValueMapping]:
        """Neo4j :ValueMapping CONTAINS 검색"""
        ...

    async def find_similar_queries(
        self,
        question_vector: list[float],
        tenant_id: str,
        top_k: int = 5,
    ) -> list[CachedQuery]:
        """Neo4j :Query 벡터 유사도 검색"""
        ...
```

### 6.3 SIMILAR_TO 관계 자동 생성

벡터 유사도 기반 :Query 노드 간 관계 생성:

```cypher
-- Synapse 측에서 실행 (Oracle에서는 ACL 호출만)
MATCH (q1:Query {id: $new_query_id})
CALL db.index.vector.queryNodes('query_question_vec_index', 5, q1.vector_question)
YIELD node AS q2, score
WHERE q2.id <> q1.id AND score >= 0.85
MERGE (q1)-[r:SIMILAR_TO]->(q2)
SET r.cosine_score = score, r.created_at = datetime()
```

### 6.4 유사 쿼리 활용 (SQL 생성 시)

```python
# nl2sql_pipeline.py — _search_and_catalog 확장
async def _search_and_catalog(self, question, question_vector, tenant_id, datasource_id, case_id=None):
    ...
    # 기존: search_result.cached_queries
    # 신규: 벡터 기반 유사 쿼리 추가 검색
    if question_vector:
        vector_similar = await oracle_synapse_acl.find_similar_queries(
            question_vector=question_vector,
            tenant_id=tenant_id,
            top_k=3,
        )
        for sq in vector_similar:
            if sq.question not in {cq.question for cq in similar_queries}:
                similar_queries.append({"question": sq.question, "sql": sq.sql, "confidence": sq.confidence})
    ...
```

---

## 7. Neo4j 스키마 변경 사항

### 7.1 신규 제약조건 + 인덱스

Synapse의 Neo4j bootstrap에 추가해야 할 항목:

```cypher
-- :Query 노드 (이미 KAIR에 존재 — Axiom의 Synapse에 이식)
CREATE CONSTRAINT query_id IF NOT EXISTS
FOR (q:Query) REQUIRE q.id IS UNIQUE;

CREATE INDEX query_question_idx IF NOT EXISTS
FOR (q:Query) ON (q.question);

CREATE INDEX query_created_idx IF NOT EXISTS
FOR (q:Query) ON (q.created_at);

CREATE VECTOR INDEX query_question_vec_index IF NOT EXISTS
FOR (q:Query) ON (q.vector_question)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

-- :ValueMapping 노드 (이미 KAIR에 존재 — Axiom의 Synapse에 이식)
CREATE CONSTRAINT value_mapping_key IF NOT EXISTS
FOR (v:ValueMapping) REQUIRE (v.natural_value, v.column_fqn) IS NODE KEY;

CREATE INDEX value_mapping_natural_idx IF NOT EXISTS
FOR (v:ValueMapping) ON (v.natural_value);
```

### 7.2 :Query 노드 프로퍼티

| 프로퍼티 | 타입 | 설명 |
|----------|------|------|
| id | string | MD5(datasource_id + question)[:12] |
| question | string | 원본 질문 |
| question_norm | string | 정규화된 질문 (whitespace 정리) |
| sql | string | 최종 SQL |
| status | string | "completed" / "error" |
| row_count | int | 실행 결과 행 수 |
| execution_time_ms | float | 실행 시간 |
| verified | boolean | 품질 게이트 검증 여부 |
| verified_confidence | float | 검증 confidence |
| verified_source | string | "quality_gate" / "manual" |
| quality_gate_json | string | 심사 결과 JSON |
| vector_question | list[float] | 질문 임베딩 벡터 |
| created_at | datetime | 생성 시각 |
| last_seen_at | datetime | 최종 조회 시각 |
| seen_count | int | 조회 횟수 |
| tables_used | list[string] | 사용 테이블 목록 |
| columns_used | list[string] | 사용 컬럼 FQN 목록 |

### 7.3 :ValueMapping 노드 프로퍼티

| 프로퍼티 | 타입 | 설명 |
|----------|------|------|
| natural_value | string | 자연어 값 (복합 키 1) |
| column_fqn | string | 컬럼 FQN (복합 키 2) |
| code_value | string | 실제 DB 값 |
| usage_count | int | 사용 횟수 |
| verified | boolean | 검증 여부 |
| verified_confidence | float | 검증 confidence |
| verified_source | string | 출처 |
| updated_at | datetime | 최종 갱신 시각 |

### 7.4 관계 타입

| 관계 | 출발 | 도착 | 프로퍼티 |
|------|------|------|----------|
| USES_TABLE | :Query | :Table | - |
| SELECTS | :Query | :Column | - |
| FILTERS | :Query | :Column | op, value |
| AGGREGATES | :Query | :Column | fn |
| GROUPS_BY | :Query | :Column | - |
| JOINS_ON | :Query | :Column | - |
| MAPS_TO | :ValueMapping | :Column | - |
| SIMILAR_TO | :Query | :Query | cosine_score, created_at |

---

## 8. 테스트 계획

### 8.1 단위 테스트

| 대상 | 파일 | 테스트 항목 |
|------|------|-------------|
| QualityJudge | `tests/test_quality_judge.py` | LLM 응답 파싱 (정상/비정상/빈값), fail-closed 동작, confidence 범위, N-라운드 로직 |
| semantic_mismatch_reasons | `tests/test_quality_judge.py` | 집계 누락 감지 (AVG/SUM/COUNT), GROUP BY 누락 감지 |
| ValueMappingService | `tests/test_value_mapping_service.py` | 3단계 파이프라인, 한국어 조사 제거, DB probe timeout, 빈 결과 |
| expand_search_terms | `tests/test_value_mapping_service.py` | 조사 제거 ("서울의" → "서울"), 행정구역 ("청주시" → "청주") |
| ConversationState | `tests/test_conversation_state.py` | 턴 추가, MAX_TURNS 초과, 컨텍스트 선택 (Jaccard), 직렬화/역직렬화 |
| ConversationStore | `tests/test_conversation_store.py` | Redis get/save/delete, TTL 만료, 세션 ID 생성 |
| GateDecision | `tests/test_cache_postprocess.py` | APPROVE/PENDING/REJECT 분기, persist 호출 조건 |

### 8.2 통합 테스트

| 시나리오 | 검증 내용 |
|----------|-----------|
| 정상 쿼리 + APPROVE | 품질 게이트 → APPROVE → Neo4j 저장 + ValueMapping 학습 |
| 잘못된 SQL + REJECT | 품질 게이트 → REJECT → Neo4j 미저장 |
| 멀티턴 후속 질문 | session_id 전달 → 이전 컨텍스트 주입 → SQL에 이전 필터 반영 |
| Value Mapping 학습 | 1차 쿼리에서 DB probe → 2차 쿼리에서 Neo4j mapping 활용 |
| 유사 쿼리 검색 | 새 쿼리 → 벡터 유사도 → SIMILAR_TO 관계 생성 |

### 8.3 에지 케이스

| 케이스 | 기대 동작 |
|--------|-----------|
| LLM 호출 실패 | fail-closed → REJECT |
| LLM 응답이 JSON이 아님 | 파싱 실패 → REJECT |
| LLM 응답에 추가 키 포함 | Pydantic `extra="forbid"` → 파싱 실패 → REJECT |
| preview가 모든 NULL | confidence 하향 → 대부분 REJECT |
| row_count=0 | confidence=0 → REJECT |
| Redis 연결 실패 | 멀티턴 disabled (graceful degradation) |
| session_id 변조 시도 | user_id 불일치 → 컨텍스트 무시 |
| DB probe timeout | 2초 초과 → 해당 용어 건너뜀 |

---

## 9. 보안 고려사항

### 9.1 멀티턴 토큰 변조 방지

**위험**: KAIR는 비서명 토큰을 사용하여 클라이언트가 대화 상태를 변조할 수 있음.

**Axiom 대응**:
1. **서버 사이드 저장**: Redis에 대화 상태 저장 → 클라이언트는 `session_id`만 보유
2. **소유자 검증**: `ConversationState.user_id == JWT.sub` 확인 필수
3. **세션 ID 불투명화**: UUID v4 사용 (예측 불가)
4. **TTL 강제**: 30분 Redis TTL → 세션 자동 만료
5. **데이터소스 바운딩**: `ConversationState.datasource_id` 일치 확인

### 9.2 DB Probe SQL Injection 방지

**위험**: 사용자 질문에서 추출한 검색어가 DB probe SQL에 직접 삽입됨.

**대응**:
1. **파라미터 바인딩**: SQL에 직접 문자열 삽입 대신 `$1` 파라미터 사용
2. **sql_guard 통과**: 모든 DB probe SQL도 `sql_guard.guard_sql()` 적용
3. **읽기 전용**: `SELECT DISTINCT` + `LIMIT 10` 강제
4. **타임아웃**: 2초 하드 제한

```python
# 안전한 DB probe (파라미터 바인딩)
probe_sql = 'SELECT DISTINCT "{col}" FROM "{table}" WHERE "{col}" ILIKE $1 LIMIT 10'
params = [f"%{term}%"]
# sql_executor가 파라미터 바인딩 지원해야 함
```

### 9.3 LLM 프롬프트 인젝션 방지

**위험**: 사용자 질문에 품질 게이트를 우회하는 프롬프트 인젝션 포함 가능.

**대응**:
1. **질문 격리**: system_prompt와 user_prompt 분리 (LangChain SystemMessage/HumanMessage)
2. **출력 스키마 강제**: `extra="forbid"` → 예상치 못한 키 금지
3. **fail-closed**: 어떤 파싱 오류든 → REJECT
4. **confidence 범위 강제**: `_clamp01()` → 0.0~1.0 외 값 차단

### 9.4 캐시 오염 방지

**위험**: 잘못된 SQL이 Neo4j에 저장되면 후속 유사 쿼리 검색을 오염.

**대응**:
1. **verified 플래그**: 품질 게이트 APPROVE만 `verified=True`
2. **유사 쿼리 검색 시 필터**: `WHERE q.verified = true` 조건 추가
3. **PENDING 쿼리 격리**: 검색 결과에서 제외 또는 낮은 가중치
4. **Overwrite 정책**: KAIR의 `candidate_rank` 로직 — 더 좋은 결과가 기존을 대체

---

## 10. 구현 순서 및 의존성

### Phase 1 (Week 1-2): 품질 게이트 활성화

| 순서 | 작업 | 파일 | 의존성 | 복잡도 |
|------|------|------|--------|--------|
| 1.1 | QualityJudgeLLMOutput/QualityJudgeResult 모델 정의 | `core/quality_judge.py` (신규) | 없음 | Low |
| 1.2 | semantic_mismatch_reasons 구현 | `core/quality_judge.py` | 없음 | Low |
| 1.3 | 품질 게이트 프롬프트 작성 | `prompts/quality_gate_prompt.md` (신규) | 없음 | Medium |
| 1.4 | QualityJudge.judge_round 구현 | `core/quality_judge.py` | 1.1, 1.3 | Medium |
| 1.5 | QualityJudge.multi_round_judge 구현 | `core/quality_judge.py` | 1.4 | Medium |
| 1.6 | GateDecision 모델 확장 | `pipelines/cache_postprocess.py` | 1.1 | Low |
| 1.7 | CachePostProcessor.quality_gate 교체 | `pipelines/cache_postprocess.py` | 1.5, 1.6 | Medium |
| 1.8 | ReactAgent.run_step_quality 교체 | `pipelines/react_agent.py` | 1.4 | Low |
| 1.9 | 단위 테스트 | `tests/test_quality_judge.py` (신규) | 1.1~1.8 | Medium |

### Phase 2 (Week 2-3): Value Mapping 활성화

| 순서 | 작업 | 파일 | 의존성 | 복잡도 |
|------|------|------|--------|--------|
| 2.1 | ValueMapping 모델 확장 (verified, source) | `core/value_mapping.py` | 없음 | Low |
| 2.2 | ResolvedValue 모델 + expand_search_terms 구현 | `core/value_mapping_service.py` (신규) | 없음 | Low |
| 2.3 | ValueMappingService.resolve_values 3단계 파이프라인 | `core/value_mapping_service.py` | 2.2 | High |
| 2.4 | ValueMappingService._db_probe 구현 | `core/value_mapping_service.py` | 2.3 | Medium |
| 2.5 | ValueMappingService.validate_sql_literals 구현 | `core/value_mapping_service.py` | 2.2 | Medium |
| 2.6 | Synapse ACL: save_value_mapping, find_value_mappings 추가 | `infrastructure/acl/synapse_acl.py` | 2.1 | Medium |
| 2.7 | NL2SQLPipeline 통합 (resolve + validate + learn) | `pipelines/nl2sql_pipeline.py` | 2.3~2.6, 1.7 | High |
| 2.8 | 단위/통합 테스트 | `tests/test_value_mapping_service.py` (신규) | 2.1~2.7 | Medium |

### Phase 3 (Week 3-4): 멀티턴 대화

| 순서 | 작업 | 파일 | 의존성 | 복잡도 |
|------|------|------|--------|--------|
| 3.1 | TurnState/ConversationState 모델 | `core/conversation_state.py` (신규) | 없음 | Low |
| 3.2 | build_context_for_followup (Jaccard 선택) | `core/conversation_state.py` | 3.1 | Medium |
| 3.3 | ConversationStore (Redis CRUD + TTL) | `core/conversation_store.py` (신규) | 3.1 | Medium |
| 3.4 | API 변경 (session_id 필드 추가) | `api/text2sql.py` | 3.3 | Low |
| 3.5 | NL2SQLPipeline 통합 (컨텍스트 로드 + 저장) | `pipelines/nl2sql_pipeline.py` | 3.2, 3.3 | Medium |
| 3.6 | 대화 컨텍스트 프롬프트 포맷팅 | `pipelines/nl2sql_pipeline.py` | 3.5 | Low |
| 3.7 | ReactAgent 통합 | `pipelines/react_agent.py` | 3.2, 3.3 | Medium |
| 3.8 | 단위/통합 테스트 | `tests/test_conversation_*.py` (신규) | 3.1~3.7 | Medium |

### Phase 4 (Week 4-5): 쿼리 벡터화 + 클러스터링

| 순서 | 작업 | 파일 | 의존성 | 복잡도 |
|------|------|------|--------|--------|
| 4.1 | Synapse ACL: save_query_node, find_similar_queries 추가 | `infrastructure/acl/synapse_acl.py` | 없음 | Medium |
| 4.2 | Neo4j 스키마 bootstrap (Synapse 측) | Synapse 서비스 | 4.1 | Medium |
| 4.3 | CachePostProcessor.persist_query 확장 (벡터 저장) | `pipelines/cache_postprocess.py` | 4.1, 1.7 | Medium |
| 4.4 | SIMILAR_TO 관계 생성 (Synapse 측) | Synapse 서비스 | 4.2 | Medium |
| 4.5 | NL2SQLPipeline 유사 쿼리 검색 강화 | `pipelines/nl2sql_pipeline.py` | 4.1 | Low |
| 4.6 | 통합 테스트 | `tests/test_query_vectorization.py` (신규) | 4.1~4.5 | Medium |

### 의존성 그래프

```
Phase 1 (품질 게이트)
  │
  ├─► Phase 2 (Value Mapping) ─── 1.7(quality_gate) 필요: 학습 매핑 저장 시 verified 판정
  │
  └─► Phase 3 (멀티턴) ─── 독립적이나 1.8(ReactAgent quality) 이후 권장

Phase 2 + Phase 1
  │
  └─► Phase 4 (벡터화) ─── 1.7(persist_query)과 2.6(save_value_mapping) 필요
```

---

## 변경 파일 요약

### 신규 파일 (6개)
| 파일 | 목적 |
|------|------|
| `services/oracle/app/core/quality_judge.py` | LLM 기반 품질 심사 로직 |
| `services/oracle/app/prompts/quality_gate_prompt.md` | 품질 게이트 LLM 프롬프트 |
| `services/oracle/app/core/value_mapping_service.py` | 3단계 Value Mapping 서비스 |
| `services/oracle/app/core/conversation_state.py` | 멀티턴 대화 상태 모델 |
| `services/oracle/app/core/conversation_store.py` | Redis 기반 대화 저장소 |
| `services/oracle/app/prompts/` (디렉토리) | 프롬프트 템플릿 디렉토리 |

### 수정 파일 (6개)
| 파일 | 변경 내용 |
|------|-----------|
| `services/oracle/app/pipelines/cache_postprocess.py` | quality_gate → LLM 심사, GateDecision 확장, persist_query 벡터 저장 |
| `services/oracle/app/core/value_mapping.py` | 모델 확장 (verified, source), 스텁 로직 제거 |
| `services/oracle/app/pipelines/nl2sql_pipeline.py` | Value Mapping 통합, 대화 컨텍스트 로드/저장, 유사 쿼리 검색 강화 |
| `services/oracle/app/pipelines/react_agent.py` | run_step_quality → QualityJudge, 대화 컨텍스트 통합 |
| `services/oracle/app/api/text2sql.py` | session_id 필드 추가, 응답에 session_id 포함 |
| `services/oracle/app/infrastructure/acl/synapse_acl.py` | save_query_node, save_value_mapping, find_value_mappings, find_similar_queries 추가 |
