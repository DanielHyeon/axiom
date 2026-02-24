# Synapse Full 스펙 구현 계획 (미구현·스텁·갭 항목)

> **근거**: [docs/05_backlog/future-backlog.md](../../future-implementation-backlog.md) §3, [docs/03_implementation/synapse/](.) (00~99 구현 계획), services/synapse/docs 및 **코드 검증 결과**  
> **범위**: 현재 스텁·인메모리·설계 미달인 항목만. 설계 문서를 참조하여 단계별 구현 계획을 수립한다.  
> **작성일**: 2026-02-23  
> **구현 상태 (코드 기준 2026-02 검증)**: Event Log·Process Mining·Extraction·Graph·Ontology·Schema-edit API 라우트 및 서비스 계층 존재. **S5·S1·S4·S2·S3·S6·S7 구현 완료**: Neo4j 부트스트랩, Event Log 영속, Mining Task/Result·참조 모델 영속, Discover pm4py 연동, Conformance 진단 형식, Extraction NER 실연동, Ontology Ingest(Redis axiom:events 소비·case.* → Neo4j MERGE).

---

## 1. 목적

- Synapse의 **미구현**, **스텁**, **인메모리 한계** 또는 **설계 문서 대비 갭**인 항목을 services/synapse/docs 및 docs/03_implementation/synapse에 맞춰 Full 스펙으로 구현하기 위한 계획.
- Phase별 설계 문서 참조, 티켓, 선행 조건, 통과 기준을 명시.

---

## 2. 참조 설계 문서

| 문서 | 용도 |
|------|------|
| **02_api/event-log-api.md** | Event Log 인제스트(CSV/XES/DB), 비동기 task_id, 컬럼 매핑, 통계·미리보기·권한 |
| **02_api/process-mining-api.md** | Discover/Conformance/Variants/Bottlenecks/Performance, 비동기 작업, BPMN export, import-model |
| **02_api/extraction-api.md** | 추출 파이프라인, HITL, revert-extraction(Saga), 권한 |
| **02_api/graph-api.md** | 벡터/FK/온톨로지 검색 |
| **02_api/ontology-api.md** | 온톨로지 CRUD |
| **02_api/schema-edit-api.md** | 스키마 편집 |
| **03_backend/process-discovery.md** | pm4py Alpha/Heuristic/Inductive, Petri Net→BPMN, Neo4j 저장 |
| **03_backend/conformance-checker.md** | Token-based replay, fitness/precision/generalization/simplicity, 편차 리포트 |
| **03_backend/ontology-ingest.md** | Redis Streams 소비, 케이스 이벤트→Neo4j MERGE |
| **03_backend/neo4j-bootstrap.md** | 스키마/제약/인덱스 초기화 |
| **03_backend/service-structure.md** | 서비스 계층·리포지토리 |
| **06_data/neo4j-schema.md** | Neo4j 스키마 |
| **docs/02_api/service-endpoints-ssot.md** §2.1 | Core→Synapse 경로 (process-mining/discover 등) |

> 위 02_api, 03_backend, 06_data 문서는 **services/synapse/docs/** 기준 상대 경로이다.

---

## 3. 갭 요약 (코드 기준)

| 영역 | 현재 상태 (코드) | Full 스펙 (설계 문서) |
|------|------------------|------------------------|
| **Event Log 저장** | **인메모리**: `EventLogService._logs`, `_task_to_log`. 재시작 시 소실. | event-log-api: 영속 저장(PostgreSQL 또는 설계된 스키마). task_id 기반 비동기 인제스트 상태 폴링. |
| **Event Log 인제스트** | CSV/XES/DB 소스 구현. 동기 처리 후 즉시 `status: "ingesting"` 반환(실제 레코드는 이미 `completed`). | 비동기: 202 + task_id, 폴링으로 completed/failed 확인. |
| **Process Discover** | **pm4py 미연동**: `process_mining_service.submit_discover`는 `_summarize_model`(활동/전이 집합) + `_build_bpmn_xml`(선형 태스크 체인). `app/mining/process_discovery.py`에 pm4py alpha/heuristic/inductive·BPMN 내보내기 구현되어 있으나 **서비스에서 import/호출 없음**. | process-discovery.md: pm4py Alpha/Heuristic/Inductive 선택, Petri Net 통계, BPMN 변환, Neo4j 저장. |
| **Process Conformance** | **경량 구현**: `conformance_checker.check_conformance(events, designed_activities)` — 설계 활동 시퀀스 vs trace 비교만. `CaseDiagnostic`: missing_tokens, remaining_tokens, consumed_tokens, produced_tokens (trace/deviations 배열 없음). | conformance-checker.md: Token-based replay, Petri Net 참조 모델, fitness/precision/generalization/simplicity, case_diagnostics에 trace·deviations( position, expected, actual, type, description). |
| **참조 모델 로드** | `_resolve_reference_activities`: eventstorming/petri_net 시 `self._models`(인메모리) 또는 discovered 결과 또는 **폴백**으로 로그의 most_common trace 사용. EventStorming/Neo4j에서 참조 모델 로드 미구현. | process-mining-api: reference_model.type eventstorming, model_id로 참조 모델 조회(저장소/Neo4j). |
| **Mining Task/Result 저장** | **인메모리**: `ProcessMiningService._tasks`, `_results`, `_models`. 재시작 시 소실. | 영속 저장(DB 또는 설계된 스키마), 동시 작업 제한·폴링 안정성. |
| **Neo4j 부트스트랩** | `main.py` lifespan에서 `Neo4jBootstrap(neo4j_client)` 생성 후 `# await bootstrap.initialize()` **주석 처리** → 스타트업 시 스키마/제약/인덱스 미적용. | neo4j-bootstrap.md: idempotent 스키마 버전·제약·벡터 인덱스·온톨로지 제약 생성. |
| **Extraction NER** | `app/extraction/ner_extractor.py`: `NERExtractor.extract_entities` **Mock** — `return DocumentExtractionResponse()`. | extraction-api, extraction-pipeline: 텍스트→청킹→LLM NER→관계 추출→온톨로지 매핑→Neo4j commit. |
| **Ontology Ingest** | **구현됨**: `app/events/consumer.py`에서 axiom:events(synapse_group) 소비, case.*만 처리. `ontology_ingest.process_event` + `merge_from_ingest_result`로 Neo4j MERGE. REDIS_URL 비어 있으면 소비 비활성화. | ontology-ingest.md: case.* 이벤트 소비, Neo4j MERGE. |
| **Core 연동** | Core `event_log` Worker: Synapse `POST /api/v3/synapse/event-logs/ingest` multipart 호출 구현. SSOT §2.1 경로 일치. | gateway-api: Core 게이트웨이 경유 시 `/api/v1/event-logs` 등. |

---

## 4. Phase 개요

| Phase | 목표 | 설계 문서 | 선행 | 상태 |
|-------|------|-----------|------|------|
| **S1** | Event Log 영속 저장 + 비동기 인제스트 | event-log-api.md | - | 완료(영속 저장; 비동기 폴링은 선택) |
| **S2** | Process Discover pm4py 연동 | process-discovery.md, process-mining-api.md | S1(선택, log_id 영속) | 완료 |
| **S3** | Conformance Token Replay + 진단 형식 | conformance-checker.md, process-mining-api.md | 참조 모델 저장소(import-model 또는 S4) | 완료(진단 형식; token_replay 선택) |
| **S4** | Mining Task/Result·참조 모델 영속 + 참조 모델 로드 | process-mining-api.md, process-discovery.md | - | 완료 |
| **S5** | Neo4j 부트스트랩 활성화 | neo4j-bootstrap.md | - | 완료 |
| **S6** | Extraction NER/파이프라인 실연동 | extraction-api.md, 01_architecture/extraction-pipeline.md | LLM 설정 | 완료 |
| **S7** | Ontology Ingest 이벤트 소비 (선택) | ontology-ingest.md | Core 이벤트 발행 | 완료 |

---

## 5. Phase S1: Event Log 영속 저장 + 비동기 인제스트

**목표**: Event Log 메타데이터·이벤트를 영속 저장하고, 인제스트를 비동기(task_id 폴링)로 전환.

### 5.1 참조 설계

- **event-log-api.md**: POST /ingest → 202 + task_id; GET /tasks/{task_id} 또는 상태 필드로 completed/ingesting/failed; GET /, GET /{log_id}, GET /{log_id}/statistics, GET /{log_id}/preview, PUT /{log_id}/column-mapping, POST /{log_id}/refresh.
- **06_data/event-log-schema.md** (존재 시): PostgreSQL 테이블 정의.

### 5.2 선행 조건

- Synapse용 DB(PostgreSQL 등) 스키마 결정. 없으면 설계 문서에 맞춰 event_logs, event_log_events(또는 단일 테이블) 등 정의.

### 5.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S1-1 | Event Log 영속 스키마 | event_logs( log_id, tenant_id, case_id, name, source_type, status, column_mapping, created_at, updated_at 등), 이벤트 저장(로그별 이벤트 테이블 또는 JSONB). | 마이그레이션/스키마 파일 |
| S1-2 | EventLogService 저장소 연동 | _logs 대신 DB 조회/저장. list_logs, get_log, get_events_for_mining, get_statistics, get_preview, update_column_mapping, refresh, delete_log. | event_log_service.py, event_log_db.py 확장 또는 repository |
| S1-3 | 비동기 인제스트 흐름 | ingest 시 task 레코드 생성(queued/ingesting), 백그라운드에서 파싱·저장 후 status=completed/failed 갱신. 202 응답에 task_id. (선택) GET /tasks/{task_id} 또는 로그 상세에 status 반영. | event_log_service.ingest, 백그라운드 태스크 또는 Worker |
| S1-4 | Core Worker 호환 유지 | Core event_log Worker의 multipart ingest 호출 후 응답 202 수용. 필요 시 동기 완료 옵션 또는 폴링 안내. | - |

### 5.4 통과 기준 (Gate S1)

- Event Log 생성 후 서비스 재시작해도 목록/상세/통계/미리보기가 유지된다.
- POST /ingest는 202 + task_id를 반환하며, 대용량 시 비동기로 완료 상태가 갱신된다(또는 문서화된 제한 내 동기 완료).

---

## 6. Phase S2: Process Discover pm4py 연동

**목표**: submit_discover에서 app/mining/process_discovery의 pm4py 기반 discovery 사용. 알고리즘(alpha/heuristic/inductive)별 Petri Net·BPMN 생성.

### 6.1 참조 설계

- **process-discovery.md**: discover_with_alpha, discover_with_heuristic, discover_with_inductive; generate_bpmn; 통계(places, transitions, arcs).
- **process-mining-api.md** §3.1: algorithm, parameters(noise_threshold, dependency_threshold), options(generate_bpmn, calculate_statistics, store_in_neo4j).

### 6.2 선행 조건

- (권장) S1으로 log_id 영속화. 없으면 기존 인메모리 로그로 동작 가능하나 재시작 시 결과 소실.

### 6.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S2-1 | 이벤트→pm4py DataFrame 변환 | event_log_service.get_events_for_mining 반환 형식을 pm4py 표준 컬럼(case:concept:name, concept:name, time:timestamp) DataFrame으로 변환. event-log-api §4 참고. | process_mining_service 또는 공용 변환 유틸 |
| S2-2 | discover 경로에서 process_discovery 호출 | submit_discover 내부에서 algorithm에 따라 discover_with_alpha/heuristic/inductive 호출. DataFrame 전달, 결과 Petri Net 통계·BPMN 문자열 반환. | process_mining_service.submit_discover |
| S2-3 | BPMN 내보내기 | process_discovery.generate_bpmn 또는 pm4py BPMN exporter 사용. options.generate_bpmn false 시 생략. | submit_discover 결과에 bpmn_xml 포함 |
| S2-4 | (선택) Neo4j 저장 | options.store_in_neo4j true 시 발견된 모델 노드/관계 저장. process-discovery.md §4, neo4j-schema.md. | process_mining_service 또는 mining/neo4j_writer |

### 6.4 통과 기준 (Gate S2)

- POST /discover with algorithm=inductive(또는 alpha/heuristic) 호출 시 pm4py로 생성된 Petri Net 통계 및 BPMN XML이 결과에 포함된다. 기존 _summarize_model 경로 제거 또는 옵션으로만 유지.

---

## 7. Phase S3: Conformance Token Replay + 진단 형식

**목표**: Conformance를 설계대로 Token-based replay(Petri Net 기준) 또는 명세에 맞는 case_diagnostics(trace, deviations) 형식으로 제공.

### 7.1 참조 설계

- **conformance-checker.md**: token_based_replay, fitness_token_based_replay; precision/generalization/simplicity; case_diagnostics에 trace, deviations(position, expected, actual, type, description).
- **process-mining-api.md** §3.2: reference_model.type(eventstorming, petri_net, discovered), options.method token_replay, case_diagnostics 배열 형식.

### 7.2 선행 조건

- 참조 모델을 Petri Net 또는 활동 목록으로 확보 가능(S4 import-model 영속 또는 EventStorming 연동).

### 7.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S3-1 | case_diagnostics 응답 형식 정렬 | ConformanceResult의 case_diagnostics를 API 명세대로 trace(활동 이름 배열), deviations( position, expected, actual, type(skipped_activity/unexpected_activity), description ) 포함하도록 변경. | conformance_checker.py, process_mining_service 결과 매핑 |
| S3-2 | (선택) pm4py Token-based Replay | 참조 모델이 Petri Net인 경우 pm4py.conformance_diagnostics_token_based_replay, fitness_token_based_replay 호출. reference_model.discovered 또는 import-model로 Petri Net 확보. | conformance_checker 또는 process_mining_service |
| S3-3 | 참조 모델 EventStorming/저장소 로드 | _resolve_reference_activities에서 eventstorming/petri_net + model_id 시 DB 또는 Neo4j에서 활동 시퀀스/모델 로드. 현재 _models 인메모리 + 폴백 제거 또는 보완. | process_mining_service._resolve_reference_activities |

### 7.4 통과 기준 (Gate S3)

- POST /conformance 응답의 case_diagnostics에 trace, deviations가 포함되어 설계 문서·API 예시와 일치한다.
- (선택) Token-based replay 사용 시 fitness/precision 등이 pm4py 결과와 정합된다.

---

## 8. Phase S4: Mining Task/Result·참조 모델 영속 + 참조 모델 로드

**목표**: ProcessMiningService의 _tasks, _results, _models를 영속 저장하고, reference_model 조회를 저장소 기반으로 전환.

### 8.1 참조 설계

- **process-mining-api.md**: GET /tasks/{task_id}, GET /tasks/{task_id}/result, POST /import-model; reference_model.model_id.
- **03_backend/service-structure.md**: 서비스·리포지토리 분리.

### 8.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S4-1 | Mining Task/Result 스키마 | mining_tasks( task_id, tenant_id, task_type, case_id, log_id, status, result_id, created_at, completed_at, error ), mining_results( result_id, task_id, result payload ). | 마이그레이션/스키마 |
| S4-2 | ProcessMiningService 저장소 연동 | _tasks, _results를 DB에 저장·조회. submit_*, get_task, get_task_result, get_result. | process_mining_service.py, repository |
| S4-3 | Import된 모델 영속 | _models를 DB(또는 별도 테이블)에 저장. import_model 시 영속, _resolve_reference_activities에서 model_id로 조회. | process_mining_service, import_model·_resolve_reference_activities |
| S4-4 | 동시 작업 제한 유지 | _max_active_tasks를 DB 기반 queued/running 카운트로 적용. | process_mining_service |

### 8.3 통과 기준 (Gate S4)

- discover/conformance 등 호출 후 재시작해도 GET /tasks/{task_id}, GET /tasks/{task_id}/result로 결과를 조회할 수 있다.
- POST /import-model 후 reference_model.model_id로 conformance를 요청하면 해당 모델이 사용된다.

---

## 9. Phase S5: Neo4j 부트스트랩 활성화

**목표**: 서비스 기동 시 Neo4j 스키마/제약/인덱스를 안정적으로 적용.

### 9.1 참조 설계

- **neo4j-bootstrap.md**, **app/graph/neo4j_bootstrap.py**: initialize(), _create_legacy_constraints, _create_vector_indexes, _create_ontology_constraints 등.

### 9.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S5-1 | lifespan에서 부트스트랩 호출 | main.py lifespan에서 Neo4jBootstrap.initialize() 주석 해제 및 await 호출. 실패 시 로깅 또는 기동 실패 정책 결정. | main.py |
| S5-2 | (선택) 스키마 버전 체크 | 이미 적용된 버전이 있으면 스킵 또는 마이그레이션만 실행. | neo4j_bootstrap.py |

### 9.3 통과 기준 (Gate S5)

- Synapse 기동 후 Neo4j에 제약·인덱스가 존재하며, 벡터 검색·온톨로지 레이블이 정상 동작한다.

---

## 10. Phase S6: Extraction NER/파이프라인 실연동

**목표**: NER 추출을 LLM(GPT-4o 등) 연동으로 전환하고, 추출 파이프라인(청킹→NER→관계→온톨로지 매핑→Neo4j)을 설계대로 구현.

### 10.1 참조 설계

- **extraction-api.md**: extract-ontology, ontology-status, ontology-result, confirm, review, revert-extraction.
- **01_architecture/extraction-pipeline.md**, **05_llm/entity-extraction.md**: 청킹, NER, 관계 추출, auto_commit_threshold, HITL.

### 10.2 선행 조건

- Synapse에서 사용할 LLM 설정(API 키, 모델) 확정. 구조화 출력 스키마(엔티티 타입 등) 확정.

### 10.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S6-1 | NER 실연동 | NERExtractor.extract_entities에서 LLM 호출, DocumentExtractionResponse에 entities 반환. 엔티티 타입은 extraction-api §3.1 target_entity_types 등과 정합. | ner_extractor.py |
| S6-2 | 추출 파이프라인 단계 | 텍스트 추출→청킹→NER→관계 추출→온톨로지 매핑→Neo4j commit, 상태 진행률(ontology-status) 반영. | extraction_service, pipeline 모듈 |
| S6-3 | revert-extraction 보강 | entity_ids/relation_ids 기반 Neo4j 노드/관계 삭제, status reverted, saga_context_id 멱등성. (이미 API 있으면 구현 검증.) | extraction_service, extraction-api §3.7 |

### 10.4 통과 기준 (Gate S6)

- POST /documents/{doc_id}/extract-ontology 호출 시 Mock이 아닌 실제 NER 결과가 ontology-result에 반영된다.
- POST /documents/{doc_id}/revert-extraction이 설계대로 동작한다.

---

## 11. Phase S7: Ontology Ingest 이벤트 소비 (선택) — 완료

**목표**: Redis Streams의 case.* 이벤트를 소비하여 Neo4j 온톨로지 노드를 MERGE하는 파이프라인을 가동.

### 11.1 참조 설계

- **ontology-ingest.md**: 구독 이벤트(case.created, case.updated 등), 핸들러, MERGE 규칙, 중복 방지.

### 11.2 선행 조건

- Core에서 해당 이벤트가 Redis 스트림에 발행됨. Synapse에서 Redis 연결 설정.

### 11.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| S7-1 | 이벤트 소비자 등록 | main 또는 별도 worker에서 Redis Consumer Group 구독, ontology_ingest 핸들러 호출. | main.py 또는 workers/ontology_ingest_worker.py |
| S7-2 | 핸들러 구현·MERGE | 이벤트 타입별 Neo4j MERGE 쿼리. ontology-ingest.md 매핑 규칙. | ontology_ingest.py |

### 11.4 통과 기준 (Gate S7)

- Core에서 case.* 이벤트 발행 시 Synapse가 소비하여 Neo4j에 해당 노드가 반영된다.

---

## 12. 권장 실행 순서

1. **Phase S5 (Neo4j 부트스트랩)** — 즉시 적용 가능, 다른 Phase의 Neo4j 의존성 선행.
2. **Phase S1 (Event Log 영속)** — 로그 재시작 내구성, Core Worker·Mining 연동 안정화.
3. **Phase S4 (Mining 영속)** — Task/Result/참조 모델 영속 후 S2·S3이 재시작 후에도 유효.
4. **Phase S2 (Discover pm4py)** — Process Mining 품질 향상.
5. **Phase S3 (Conformance 형식·선택 Replay)** — API 계약 및 분석 품질.
6. **Phase S6 (Extraction NER)** — 리소스·LLM 정책 확정 후.
7. **Phase S7 (Ontology Ingest)** — 완료. REDIS_URL 설정 시 axiom:events(synapse_group) 소비, Core에서 case.* 발행 시 Neo4j MERGE.

---

## 13. 문서 갱신

- 각 Phase 완료 시 **future-implementation-backlog.md** §3 Synapse 행을 코드 검증 결과에 맞게 갱신.
- **services/synapse/docs/02_api/process-mining-api.md** 구현 상태 태그(Partial/Implemented)를 Phase 완료에 따라 수정.
- **docs/02_api/service-endpoints-ssot.md** 변경 시 Synapse 경로·버전 반영.
