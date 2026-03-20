# KAIR → Axiom 갭 구현 결과 보고서

> 작성일: 2026-03-20
> 상태: **2차 검증 APPROVE** — 전체 Critical 7건, Major 9건 수정 완료

---

## 1. 구현 범위 요약

| 우선순위 | 문서 | 항목 | 서비스 | 상태 |
|----------|------|------|--------|------|
| **P0** | p0-01 | 인과 분석 엔진 | Vision | ✅ 완료 |
| **P0** | p0-02 Part A | 온톨로지 관계 가중치 + Driver 레이어 | Synapse | ✅ 완료 |
| **P0** | p0-02 Part B | What-if DAG 전파 시뮬레이션 | Vision | ✅ 완료 |
| **P1** | p1-01 #6 | SQLGlot AST 기반 SQL 검증 | Oracle | ✅ 완료 |
| **P1** | p1-01 #7 | Sub-schema Context (LLM 컨텍스트 축소) | Oracle | ✅ 완료 |
| **P1** | p1-01 #8 | Enum Cache 활성화 | Oracle | ✅ 완료 |
| **P1** | p1-02 #12 | LLM 기반 품질 게이트 | Oracle | ✅ 완료 |
| **P1** | p1-02 #13 | Value Mapping 3단계 파이프라인 | Oracle | ✅ 완료 |

---

## 2. 서비스별 변경 파일

### 2.1 Vision 서비스 (P0-1 + P0-2B)

| 파일 | 유형 | LOC | 설명 |
|------|------|-----|------|
| `engines/causal_analysis_engine.py` | 신규 | ~430 | Granger/VAR/Pearson 하이브리드 인과 분석 |
| `services/causal_data_fetcher.py` | 신규 | ~220 | Synapse 온톨로지 + Weaver 시계열 조회 |
| `api/causal.py` | 신규 | ~170 | 인과 분석 REST API (202 비동기) |
| `engines/whatif_dag_engine.py` | 신규 | ~400 | 20-wave 증분 전파 + 누적 lag 추적 |
| `engines/whatif_fallback.py` | 신규 | ~180 | sklearn 기반 ML 폴백 예측기 |
| `engines/whatif_models.py` | 신규 | ~140 | SimulationResult/Trace frozen dataclass |
| `services/model_graph_fetcher.py` | 신규 | ~130 | Synapse 모델 그래프 조회 + Redis 캐시 |
| `api/whatif_dag.py` | 신규 | ~140 | What-if DAG REST API |
| `services/vision_runtime.py` | 수정 | — | 인과 분석 실행 + 스레드 안전성 + 연결 누수 수정 |
| `services/root_cause_engine.py` | 수정 | — | causal_edges 선택적 파라미터 추가 |
| `main.py` | 수정 | — | causal + whatif_dag 라우터 등록 |
| `requirements.txt` | 수정 | — | pandas, statsmodels, scikit-learn 추가 |

### 2.2 Synapse 서비스 (P0-2A)

| 파일 | 유형 | LOC | 설명 |
|------|------|-----|------|
| `services/ontology_service.py` | 수정 | +350 | weight/lag/confidence, BehaviorModel CRUD, Driver 레이어 |
| `api/ontology.py` | 수정 | +120 | PATCH relations, BehaviorModel API, model-graph |

### 2.3 Oracle 서비스 (P1-1 + P1-2)

| 파일 | 유형 | LOC | 설명 |
|------|------|-----|------|
| `core/sql_guard.py` | 수정 | +110 | 6단계 AST 검증 파이프라인 |
| `core/schema_context.py` | 수정 | ~130 | SubSchemaContext + DDL 포맷터 |
| `core/quality_judge.py` | 수정 | ~200 | N-라운드 LLM 품질 심사 (fail-closed) |
| `core/value_mapping.py` | 수정 | ~350 | 3단계 매핑 (캐시→Enum→DB Probe) |
| `core/sql_exec.py` | 수정 | +40 | 파라미터화 쿼리 + 연결 누수 수정 |
| `pipelines/cache_postprocess.py` | 수정 | +80 | QualityJudge 연동 |
| `pipelines/react_agent.py` | 수정 | +30 | QualityJudge + NoneType 버그 수정 |
| `pipelines/nl2sql_pipeline.py` | 수정 | +50 | SubSchema + ValueMapping + 테이블 화이트리스트 |
| `pipelines/enum_cache_bootstrap.py` | 수정 | +280 | 실구현 (스텁→프로덕션) |

---

## 3. 보안 수정 근거

### 3.1 SQL Injection 방지 (Critical 5건)

| # | 위치 | 위협 | 수정 | 검증 |
|---|------|------|------|------|
| 1 | `sql_guard.py` | EXEC/MERGE 미탐지 | `exp.Command` + `exp.Merge` 금지 타입 | 58개 공격 벡터 테스트 |
| 2 | `sql_guard.py` | 멀티스테이트먼트 우회 | `parse()` → 멀티체크 → AST 순서 강제 | `test_stacked_query_*` |
| 3 | `enum_cache_bootstrap.py` | 식별자 Injection | `psycopg2.sql.Identifier` | 2차 리뷰 확인 |
| 4 | `causal_data_fetcher.py` | Weaver SQL Injection | `_SAFE_ID` 정규식 검증 | 2차 리뷰 확인 |
| 5 | `value_mapping.py` | DB Probe f-string 주입 | `$1` 파라미터 바인딩 | `test_safe_identifier_*` |

### 3.2 인가 강화 (Critical 3건)

| # | 위치 | 위협 | 수정 |
|---|------|------|------|
| 1 | `ontology.py` delete_node | 교차 테넌트 삭제 | `tenant_id` 검증 + `PermissionError` |
| 2 | `ontology.py` delete_relation | 교차 테넌트 삭제 | `tenant_id` 검증 + `PermissionError` |
| 3 | `ontology.py` _tenant | fail-open `"unknown"` | fail-closed `HTTPException(401)` |

### 3.3 데이터 무결성 (Major 6건)

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| 1 | `_normalize_relation` | `weight=0.0` falsy 무시 | `"key" in payload` 존재 검사 |
| 2 | `delete_node` | Neo4j 고아 노드 | `DETACH DELETE` 동기화 |
| 3 | `delete_relation` | Neo4j 고아 관계 | `DELETE r` 동기화 |
| 4 | `_sync_node_to_neo4j` | 예약 키 덮어쓰기 | `_RESERVED_PROPERTY_KEYS` 필터 |
| 5 | `sql_exec.py` | DB 연결 누수 | `try/finally + conn.close()` |
| 6 | `vision_runtime.py` | pivot 쿼리 연결 누수 | `finally + conn.close()` |

---

## 4. 리뷰 프로세스 요약

```
구현 계획서 5개 작성
        ↓
[Round 1] 계획서 리뷰 (5 에이전트 병렬)
  → 8 Critical, 21 Major 발견
        ↓
[구현] 5 워크스트림 병렬 실행 (worktree 격리)
  → Critical/Major를 프롬프트에 반영하여 구현
        ↓
[Round 2] 코드 리뷰 (4 에이전트 병렬)
  - code-reviewer × 3 (Vision/Synapse/Oracle)
  - code-quality-refactorer × 1
  → 8 Critical, 12 Major, 11 Minor 발견
        ↓
[수정] 리뷰 피드백 즉시 반영
        ↓
[Round 3] 최종 검증 (code-reviewer)
  → 16/16 항목 PASS → APPROVE
```

---

## 5. 테스트 현황

| 서비스 | 테스트 파일 | 테스트 수 | 주요 커버리지 |
|--------|-----------|----------|-------------|
| Vision | 6개 | 31+ | 인과 엔진, DAG 전파, 모델, 폴백, API |
| Synapse | 2개 | 38 | 가중치, BehaviorModel, Driver 레이어 |
| Oracle | 5개 | 164 | SQL 공격벡터, 품질게이트, 값매핑, Enum |
| **합계** | **13개** | **233+** | — |

---

## 6. KAIR → Axiom 이식 근거 매핑

| KAIR 모듈 | Axiom 구현 | 변환 전략 |
|-----------|-----------|----------|
| `causal_analysis.py` (576 LOC) | `causal_analysis_engine.py` (~430 LOC) | 알고리즘 보존, Vision 서비스 통합 |
| `simulation_engine.py` | `whatif_dag_engine.py` (~400 LOC) | wave→누적lag 개선, frozen dataclass |
| `sql_validator.py` | `sql_guard.py` (+110 LOC) | sqlglot AST, 6단계 파이프라인 |
| `enum_cache.py` | `enum_cache_bootstrap.py` (+280 LOC) | asyncio.to_thread, psycopg2.sql |
| `quality_gate.py` | `quality_judge.py` (~200 LOC) | N-라운드 LLM, fail-closed |
| `value_mapping.py` | `value_mapping.py` (~350 LOC) | 3단계 파이프라인, 파라미터화 쿼리 |
| `table_selector.py` | `schema_context.py` (~130 LOC) | SubSchemaContext 도메인 모델 |
| `OntologyBehaviorModel` | `ontology_service.py` (+350 LOC) | Neo4j 멀티레이블, Synapse BC 내부 |

---

## 7. 미해결 사항 (프로덕션 배포 전 권장)

| 우선순위 | 항목 | 서비스 | 설명 |
|----------|------|--------|------|
| P1 | `VisionRuntime` 클래스 분리 | Vision | God Object (1037줄) → 5+ 클래스 추출 |
| P1 | causal_results 영속화 | Vision | 인메모리 → VisionStateStore 연동 |
| P1 | asyncio.to_thread 래핑 | Oracle | sql_exec.py 동기 I/O → 비동기 래핑 |
| P2 | httpx.AsyncClient 재사용 | Vision | 매 요청 새 연결 → 클래스 레벨 공유 |
| P2 | Ontology Neo4j 하이드레이션 | Synapse | 서비스 재시작 시 데이터 자동 복구 |
| P2 | CORS 설정 제한 | Oracle | `allow_origins=["*"]` → 명시적 도메인 |
| P2 | ValueMapping 캐시 크기 제한 | Oracle | 무한 성장 dict → LRU 캐시 |
