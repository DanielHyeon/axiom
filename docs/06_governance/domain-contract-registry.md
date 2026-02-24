# Domain Event Contract Registry

## 1. 목적
- Core/Synapse/Vision/Weaver 간 이벤트 계약을 단일 규격으로 관리한다.
- 이벤트 스키마 변경 시 브레이킹 변경을 사전에 식별하고 승인 절차를 강제한다.

## 2. 필수 메타필드
- `event_name`: 도메인 이벤트 명
- `owner_service`: 계약 소유 서비스
- `version`: SemVer (`major.minor.patch`)
- `payload_schema`: JSON Schema 식별자 또는 경로
- `idempotency_key_rule`: 중복 제거 키 생성 규칙
- `retention`: 보존 기간
- `consumer_groups`: 소비자/그룹 목록

## 2.1 전체 이벤트 카탈로그 (DDD-P3-01)

### Core 서비스 이벤트 (8종)

| # | event_name | version | payload_schema | idempotency_key_rule | consumer_groups | retention | Stream |
|---|-----------|---------|---------------|---------------------|----------------|-----------|--------|
| 1 | `PROCESS_INITIATED` | 1.0.0 | core/process_initiated/v1 | event_type:aggregate_id | synapse_group, vision_analytics_group | 7d | axiom:core:events |
| 2 | `WORKITEM_COMPLETED` | 1.0.0 | core/workitem_completed/v1 | event_type:aggregate_id | synapse_group, vision_analytics_group | 7d | axiom:core:events |
| 3 | `WORKITEM_SELF_VERIFICATION_FAILED` | 1.0.0 | core/workitem_self_verification_failed/v1 | event_type:aggregate_id | watch_cep_group | 7d | axiom:core:events |
| 4 | `SAGA_COMPENSATION_COMPLETED` | 1.0.0 | core/saga_compensation_completed/v1 | event_type:aggregate_id | watch_cep_group | 7d | axiom:core:events |
| 5 | `WORKITEM_CREATED` | 1.0.0 | core/workitem_created/v1 | event_type:aggregate_id | vision_analytics_group | 7d | axiom:core:events |
| 6 | `WORKITEM_CANCELLED` | 1.0.0 | core/workitem_cancelled/v1 | event_type:aggregate_id | vision_analytics_group | 7d | axiom:core:events |
| 7 | `CASE_STATUS_CHANGED` | 1.0.0 | core/case_status_changed/v1 | event_type:aggregate_id:timestamp_ms | vision_analytics_group, synapse_group | 7d | axiom:core:events |
| 8 | `WATCH_ALERT_TRIGGERED` | 1.0.0 | core/watch_alert_triggered/v1 | event_type:aggregate_id:timestamp_ms | canvas_ws_group | 7d | axiom:watches |

### Synapse 서비스 이벤트 (4종)

| # | event_name | version | payload_schema | idempotency_key_rule | consumer_groups | retention | Stream |
|---|-----------|---------|---------------|---------------------|----------------|-----------|--------|
| 9 | `ONTOLOGY_NODE_CREATED` | 1.0.0 | synapse/ontology_node_created/v1 | event_type:aggregate_id:timestamp_ms | weaver_group, oracle_group | 7d | axiom:synapse:events |
| 10 | `ONTOLOGY_NODE_UPDATED` | 1.0.0 | synapse/ontology_node_updated/v1 | event_type:aggregate_id:timestamp_ms | weaver_group, oracle_group | 7d | axiom:synapse:events |
| 11 | `MINING_DISCOVERY_COMPLETED` | 1.0.0 | synapse/mining_discovery_completed/v1 | event_type:aggregate_id | core_group, vision_analytics_group | 7d | axiom:synapse:events |
| 12 | `CONFORMANCE_CHECK_COMPLETED` | 1.0.0 | synapse/conformance_check_completed/v1 | event_type:aggregate_id | core_group, vision_analytics_group | 7d | axiom:synapse:events |

### Vision 서비스 이벤트 (2종)

| # | event_name | version | payload_schema | idempotency_key_rule | consumer_groups | retention | Stream |
|---|-----------|---------|---------------|---------------------|----------------|-----------|--------|
| 13 | `WHATIF_SIMULATION_COMPLETED` | 1.0.0 | vision/whatif_simulation_completed/v1 | event_type:aggregate_id | core_group, canvas_ws_group | 7d | axiom:vision:events |
| 14 | `ROOT_CAUSE_DETECTED` | 1.0.0 | vision/root_cause_detected/v1 | event_type:aggregate_id | core_group, watch_cep_group | 7d | axiom:vision:events |

### Weaver 서비스 이벤트 (2종)

| # | event_name | version | payload_schema | idempotency_key_rule | consumer_groups | retention | Stream |
|---|-----------|---------|---------------|---------------------|----------------|-----------|--------|
| 15 | `METADATA_SYNC_COMPLETED` | 1.0.0 | weaver/metadata_sync_completed/v1 | event_type:aggregate_id | synapse_group, oracle_group | 7d | axiom:weaver:events |
| 16 | `DATASOURCE_SCHEMA_CHANGED` | 1.0.0 | weaver/datasource_schema_changed/v1 | event_type:aggregate_id:timestamp_ms | synapse_group | 7d | axiom:weaver:events |

### Redis Streams 토폴로지

```
axiom:core:events     → synapse_group, vision_analytics_group, watch_cep_group
axiom:synapse:events  → weaver_group, oracle_group, core_group, vision_analytics_group
axiom:vision:events   → core_group, canvas_ws_group, watch_cep_group
axiom:weaver:events   → synapse_group, oracle_group
axiom:watches         → watch_cep_group
axiom:workers         → extract_group, ocr_group, generate_group, event_log_group
```

## 3. 버전 정책
1. `major`
- payload 필수 필드 제거/타입 변경/의미 변경 시 증가
2. `minor`
- 하위 호환 필드 추가 시 증가
3. `patch`
- 설명/예시/옵션 기본값 수정 등 비기능 변경

## 4. 승인 및 검증 규칙 (Breaking-Change Flow)
- `major` 변경 시 기존 Consumer와의 호환성 충돌 체크(Zero-Collision Verification)를 파이프라인에서 자동 검증한다. 서비스 간 이벤트 계약 충돌(이름/버전 불일치)이 0건일 때만 PR을 승인한다.
- `major` 변경은 프로그램 레벨 승인(`code-reviewer`, `api-developer`, `backend-developer`)이 필요하다.
- 승인 전에는 Producer/Consumer 배포를 동시 진행하지 않는다.

## 4.1 핵심 이벤트 통과 기준 (Pass Criteria)
- 핵심 도메인 이벤트의 100%는 반드시 `owner_service`, `version`, `payload_schema`, `idempotency_key_rule`의 메타필드를 포함해야 한다. 누락된 이벤트는 병합이 거부된다.

## 5. DB 연계 규칙
- `event_outbox.event_type`는 Registry에 등록된 이름만 허용한다.
- `watch_alerts.event_type`도 동일 Registry를 참조한다.
- 이벤트 계약은 `docs/03_implementation/program/09_agent-governance-and-acceptance.md`의 Sprint Exit 증적으로 첨부한다.
