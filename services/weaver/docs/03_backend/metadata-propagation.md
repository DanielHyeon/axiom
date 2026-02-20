# 메타데이터 변경 전파

<!-- affects: backend, api -->
<!-- requires-update: 01_architecture/metadata-service.md -->

## 이 문서가 답하는 질문

- 메타데이터가 변경되면 어떤 이벤트가 발행되는가?
- 각 모듈은 어떤 이벤트에 반응하는가?
- 이벤트 발행과 소비의 신뢰성은 어떻게 보장되는가?
- 전파 실패 시 복구 전략은?

---

## 1. 변경 전파 개요

### 1.1 Why: 왜 변경 전파가 필요한가

```
[사실] Weaver는 Axiom 전체의 스키마 메타데이터 SSOT(Single Source of Truth)이다.
      Neo4j에 저장된 DataSource → Schema → Table → Column 계층 구조가 원본이며,
      Oracle, Synapse, Canvas, Vision 모듈이 이 메타데이터를 참조한다.

[문제] 메타데이터가 변경되었을 때 다른 모듈이 이를 모르면:
      - Oracle: 벡터 인덱스가 stale → NL2SQL이 삭제된 테이블을 참조하거나,
               새 테이블을 찾지 못함. 캐시된 :Query 노드가 무효한 SQL을 반환.
      - Synapse: 온톨로지-스키마 링크가 깨짐 → EventLogBinding의 source_table이
               더 이상 존재하지 않는 테이블을 가리킴.
      - Canvas: 사용자가 메타데이터 브라우저에서 이전 스키마를 보게 됨.
      - Vision: OLAP 큐브 정의의 fact/dim 테이블이 삭제되어 SQL 실행 실패.

[결정] Weaver가 메타데이터를 변경할 때 Redis Streams로 이벤트를 발행하고,
      각 모듈이 Consumer Group으로 이를 소비하여 자체 상태를 갱신한다.

[근거] ADR-004: Redis Streams 이벤트 버스 도입.
      Axiom은 이미 axiom:events, axiom:watches, axiom:process_mining 등의
      Redis Streams를 사용하므로, 동일 패턴으로 메타데이터 이벤트를 추가한다.
```

### 1.2 What: 전파 대상 이벤트

| Event Type | Trigger | 영향받는 모듈 |
|------------|---------|-------------|
| `metadata.extracted` | 메타데이터 추출 완료 (IntrospectionService.extract_metadata) | Oracle, Synapse, Canvas |
| `metadata.table.added` | 새 테이블 발견 (재추출 시 기존에 없던 테이블) | Oracle, Canvas |
| `metadata.table.removed` | 테이블 삭제 감지 (재추출 시 기존에 있던 테이블 소실) | Oracle, Synapse, Canvas |
| `metadata.column.modified` | 컬럼 타입/속성 변경 (재추출 시 dtype 또는 nullable 변경) | Oracle, Canvas |
| `metadata.description.updated` | 테이블/컬럼 설명 변경 (LLM 보강 또는 수동 수정) | Oracle (re-index vector) |
| `metadata.snapshot.created` | 스냅샷 생성 완료 | Canvas |
| `metadata.snapshot.restored` | 스냅샷 복원 완료 (메타데이터가 이전 시점으로 롤백) | Oracle, Synapse, Canvas |
| `metadata.tag.changed` | 태그 추가/삭제 (text_to_sql_is_valid 등 분류 변경) | Canvas |
| `metadata.glossary.updated` | 용어 사전 변경 (비즈니스 도메인 용어 정의 갱신) | Oracle, Synapse, Vision |

### 1.3 전체 아키텍처

```
┌─ Weaver (SSOT) ──────────────────────────────────────────────┐
│                                                                │
│  IntrospectionService ──┐                                     │
│  MetadataEnrichmentService ──┤                                │
│  SnapshotService ──────────┤  MetadataEventPublisher          │
│  CatalogService ───────────┤  (Redis XADD)                   │
│  GlossaryService ──────────┘       │                          │
│                                     │                          │
└─────────────────────────────────────┼──────────────────────────┘
                                      │
                                      ▼
┌─ Redis Stream: axiom:metadata_changes ─────────────────────────┐
│                                                                  │
│  Consumer Group: oracle-consumer    ──── Oracle 서비스           │
│  Consumer Group: synapse-consumer   ──── Synapse 서비스          │
│  Consumer Group: canvas-bridge      ──── Core Gateway → SSE     │
│  Consumer Group: vision-consumer    ──── Vision 서비스           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │ Core Gateway      │
                    │ (SSE Bridge)      │
                    │                   │
                    │ axiom:metadata_   │
                    │ changes 구독      │
                    │      ↓            │
                    │ /api/v1/events/   │
                    │ stream (SSE)      │
                    └────────┬──────────┘
                             │
                             ▼
                    ┌───────────────────┐
                    │ Canvas (React 18) │
                    │ EventSource 수신  │
                    │ → UI 자동 갱신     │
                    └───────────────────┘
```

---

## 2. Redis Stream 이벤트 구조

### 2.1 Stream 이름

```
axiom:metadata_changes
```

기존 Axiom Redis Streams 명명 규칙(`axiom:{도메인}`)을 따른다. 단일 스트림에 모든 메타데이터 이벤트를 발행하고, `tenant_id`를 페이로드에 포함하여 멀티테넌트를 지원한다.

### 2.2 이벤트 메시지 공통 필드

모든 메타데이터 이벤트는 다음 공통 구조를 따른다.

```json
{
  "event_id": "uuid",
  "event_type": "metadata.extracted",
  "tenant_id": "uuid",
  "case_id": "uuid",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:00:00Z",
  "actor": "admin@axiom.kr",
  "payload": { }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `event_id` | UUID | Yes | 이벤트 고유 ID (멱등성 키) |
| `event_type` | String | Yes | 이벤트 유형 (위 표 참조) |
| `tenant_id` | UUID | Yes | 테넌트 ID |
| `case_id` | UUID | No | 관련 케이스 ID (있는 경우) |
| `datasource_name` | String | Yes | 변경된 데이터소스 이름 |
| `timestamp` | ISO 8601 | Yes | 이벤트 발생 시각 |
| `actor` | String | Yes | 변경을 유발한 주체 (사용자 이메일 또는 "system") |
| `payload` | Object | Yes | 이벤트 유형별 상세 데이터 |

### 2.3 이벤트별 페이로드 상세

#### metadata.extracted

메타데이터 추출 완료. IntrospectionService가 Neo4j 저장을 마친 직후 발행.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440001",
  "event_type": "metadata.extracted",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:00:12Z",
  "actor": "admin@axiom.kr",
  "payload": {
    "schemas_count": 3,
    "tables_count": 45,
    "columns_count": 312,
    "foreign_keys_count": 18,
    "snapshot_id": "snap-001",
    "duration_ms": 12500,
    "engine": "postgresql",
    "diff": {
      "tables_added": ["new_products", "new_orders"],
      "tables_removed": ["deprecated_log"],
      "tables_unchanged": 42
    }
  }
}
```

#### metadata.table.added

재추출 시 기존에 없던 테이블이 발견됨.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440002",
  "event_type": "metadata.table.added",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:00:12Z",
  "actor": "system",
  "payload": {
    "schema": "public",
    "table_name": "new_products",
    "table_type": "BASE TABLE",
    "columns_count": 8,
    "row_count": 1520
  }
}
```

#### metadata.table.removed

재추출 시 기존에 있던 테이블이 소실됨.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440003",
  "event_type": "metadata.table.removed",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:00:12Z",
  "actor": "system",
  "payload": {
    "schema": "public",
    "table_name": "deprecated_log",
    "had_queries": true,
    "affected_query_count": 3
  }
}
```

#### metadata.column.modified

컬럼 타입 또는 속성이 변경됨.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440004",
  "event_type": "metadata.column.modified",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:00:12Z",
  "actor": "system",
  "payload": {
    "schema": "public",
    "table_name": "processes",
    "column_name": "status",
    "changes": {
      "dtype": {"old": "varchar(10)", "new": "varchar(20)"},
      "nullable": {"old": false, "new": true}
    }
  }
}
```

#### metadata.description.updated

테이블 또는 컬럼 설명이 변경됨 (LLM 보강 또는 수동 수정).

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440005",
  "event_type": "metadata.description.updated",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:01:00Z",
  "actor": "admin@axiom.kr",
  "payload": {
    "target_type": "table",
    "schema": "public",
    "table_name": "biz_proc_metrics",
    "column_name": null,
    "old_description": null,
    "new_description": "비즈니스 프로세스 성과 지표. 각 조직의 프로세스별 측정 유형, 수치, 활성 상태를 관리한다.",
    "source": "llm_enrichment"
  }
}
```

#### metadata.snapshot.created

메타데이터 스냅샷 생성 완료.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440006",
  "event_type": "metadata.snapshot.created",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:00:15Z",
  "actor": "admin@axiom.kr",
  "payload": {
    "snapshot_id": "snap-002",
    "tables_count": 45,
    "columns_count": 312,
    "label": "추출 후 자동 스냅샷"
  }
}
```

#### metadata.snapshot.restored

메타데이터가 이전 스냅샷으로 복원됨. 전체 메타데이터가 롤백되므로 가장 영향이 큰 이벤트.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440007",
  "event_type": "metadata.snapshot.restored",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T11:00:00Z",
  "actor": "admin@axiom.kr",
  "payload": {
    "snapshot_id": "snap-001",
    "restored_from": "2026-02-19T10:00:00Z",
    "tables_count": 42,
    "columns_count": 290,
    "diff_from_current": {
      "tables_added": 0,
      "tables_removed": 3,
      "columns_changed": 5
    }
  }
}
```

#### metadata.tag.changed

테이블/컬럼에 태그가 추가되거나 삭제됨.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440008",
  "event_type": "metadata.tag.changed",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:05:00Z",
  "actor": "admin@axiom.kr",
  "payload": {
    "target_type": "table",
    "schema": "public",
    "table_name": "temp_import_log",
    "tag_name": "text_to_sql_is_valid",
    "action": "removed",
    "old_value": true,
    "new_value": false
  }
}
```

#### metadata.glossary.updated

비즈니스 도메인 용어 사전이 변경됨.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440009",
  "event_type": "metadata.glossary.updated",
  "tenant_id": "t-001",
  "datasource_name": "erp_db",
  "timestamp": "2026-02-20T10:10:00Z",
  "actor": "admin@axiom.kr",
  "payload": {
    "action": "upsert",
    "term": "매출",
    "definition": "상품/서비스 판매로 발생한 수익 총액",
    "synonyms": ["수익", "매출액", "revenue"],
    "related_columns": ["public.biz_proc_metrics.mtr_value"],
    "previous_definition": null
  }
}
```

---

## 3. 이벤트 발행 (Producer)

### 3.1 Weaver 내부 발행 지점

| 서비스 메서드 | 발행 이벤트 | 발행 시점 |
|-------------|-----------|----------|
| `IntrospectionService.extract_metadata()` | `metadata.extracted` | Neo4j 저장 완료 직후 |
| `IntrospectionService.extract_metadata()` | `metadata.table.added` | diff 계산 후, 추가된 테이블 각각 |
| `IntrospectionService.extract_metadata()` | `metadata.table.removed` | diff 계산 후, 삭제된 테이블 각각 |
| `IntrospectionService.extract_metadata()` | `metadata.column.modified` | diff 계산 후, 변경된 컬럼 각각 |
| `MetadataEnrichmentService.enrich_datasource()` | `metadata.description.updated` | 각 테이블/컬럼 description 업데이트 후 |
| `MetadataStore.update_table_description()` | `metadata.description.updated` | 수동 설명 변경 시 |
| `MetadataStore.update_column_description()` | `metadata.description.updated` | 수동 설명 변경 시 |
| `SnapshotService.create()` | `metadata.snapshot.created` | 스냅샷 Neo4j 저장 후 |
| `SnapshotService.restore()` | `metadata.snapshot.restored` | 복원 완료 후 |
| `CatalogService.add_tag()` | `metadata.tag.changed` | 태그 변경 후 |
| `CatalogService.remove_tag()` | `metadata.tag.changed` | 태그 변경 후 |
| `GlossaryService.upsert()` | `metadata.glossary.updated` | 용어 생성/수정 후 |
| `GlossaryService.delete()` | `metadata.glossary.updated` | 용어 삭제 후 |

### 3.2 발행 코드 패턴

```python
# app/core/metadata_event_publisher.py

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class MetadataEventPublisher:
    """메타데이터 변경 이벤트를 Redis Streams로 발행하는 퍼블리셔.

    Weaver 내부에서 메타데이터가 변경될 때 호출된다.
    Core의 Event Outbox 패턴과 달리, Weaver는 PostgreSQL이 아닌
    Neo4j를 사용하므로 Outbox 테이블 없이 직접 Redis에 발행한다.

    발행 보장: at-least-once (Neo4j 커밋 후 발행)
    """

    STREAM_KEY = "axiom:metadata_changes"
    MAXLEN = 50_000  # 스트림 최대 길이 (초과 시 오래된 메시지 삭제)

    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish(
        self,
        event_type: str,
        tenant_id: str,
        datasource_name: str,
        payload: dict,
        actor: str = "system",
        case_id: Optional[str] = None,
    ) -> str:
        """메타데이터 변경 이벤트 발행.

        Args:
            event_type: 이벤트 유형 (metadata.extracted 등)
            tenant_id: 테넌트 ID
            datasource_name: 데이터소스 이름
            payload: 이벤트별 상세 데이터
            actor: 변경 주체 (사용자 이메일 또는 "system")
            case_id: 관련 케이스 ID (선택)

        Returns:
            Redis Stream entry ID

        Raises:
            이벤트 발행 실패 시 경고 로그만 남기고 예외를 전파하지 않는다.
            메타데이터 변경 자체는 Neo4j에 이미 커밋되었으므로.
        """
        event_id = str(uuid.uuid4())
        message = {
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id,
            "datasource_name": datasource_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "payload": json.dumps(payload, ensure_ascii=False),
        }
        if case_id:
            message["case_id"] = case_id

        try:
            entry_id = await self.redis.xadd(
                self.STREAM_KEY,
                message,
                maxlen=self.MAXLEN,
                approximate=True,
            )
            logger.info(
                f"Published metadata event: type={event_type} "
                f"datasource={datasource_name} entry_id={entry_id}"
            )
            return entry_id
        except Exception as e:
            # Redis 장애 시에도 메타데이터 변경을 롤백하지 않는다.
            # 소비자가 reconciliation으로 복구할 수 있다.
            logger.warning(
                f"Failed to publish metadata event: type={event_type} "
                f"datasource={datasource_name} error={e}"
            )
            return ""

    async def publish_batch(
        self,
        events: list[dict],
    ) -> list[str]:
        """여러 이벤트를 배치로 발행.

        추출 완료 시 table.added, table.removed, column.modified 등
        여러 이벤트를 한꺼번에 발행할 때 사용.

        Args:
            events: 이벤트 딕셔너리 리스트 (각각 publish()의 인자 포함)

        Returns:
            발행된 entry ID 리스트
        """
        entry_ids = []
        pipe = self.redis.pipeline()

        for event in events:
            event_id = str(uuid.uuid4())
            message = {
                "event_id": event_id,
                "event_type": event["event_type"],
                "tenant_id": event["tenant_id"],
                "datasource_name": event["datasource_name"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": event.get("actor", "system"),
                "payload": json.dumps(event["payload"], ensure_ascii=False),
            }
            if event.get("case_id"):
                message["case_id"] = event["case_id"]

            pipe.xadd(
                self.STREAM_KEY,
                message,
                maxlen=self.MAXLEN,
                approximate=True,
            )

        try:
            results = await pipe.execute()
            entry_ids = [r for r in results if r]
            logger.info(
                f"Published {len(entry_ids)} metadata events in batch"
            )
        except Exception as e:
            logger.warning(f"Failed to publish metadata event batch: {e}")

        return entry_ids
```

### 3.3 IntrospectionService 통합 예시

기존 `IntrospectionService.extract_metadata()` 완료 지점에서 이벤트를 발행한다.

```python
# app/services/introspection_service.py (발행 통합 부분)

class IntrospectionService:
    def __init__(
        self,
        metadata_store: MetadataStore,
        event_publisher: MetadataEventPublisher,
    ):
        self.metadata_store = metadata_store
        self.event_publisher = event_publisher

    async def extract_metadata(self, ...) -> AsyncGenerator[ProgressEvent, None]:
        # ... 기존 추출 로직 (스키마, 테이블, 컬럼, FK) ...

        # 5. Save to Neo4j
        save_result = await self.metadata_store.save_datasource_metadata(...)

        # 6. Diff 계산 (이전 메타데이터와 비교)
        diff = await self._compute_diff(datasource_name, previous_metadata)

        # 7. 이벤트 발행 (Neo4j 저장 완료 후)
        events = []

        # 추출 완료 이벤트 (항상 발행)
        events.append({
            "event_type": "metadata.extracted",
            "tenant_id": tenant_id,
            "datasource_name": datasource_name,
            "actor": actor,
            "payload": {
                "schemas_count": len(schemas),
                "tables_count": total_tables,
                "columns_count": len(all_columns),
                "foreign_keys_count": len(all_fks),
                "duration_ms": save_result["duration_ms"],
                "engine": engine,
                "diff": {
                    "tables_added": [t["name"] for t in diff.added_tables],
                    "tables_removed": [t["name"] for t in diff.removed_tables],
                    "tables_unchanged": diff.unchanged_count,
                },
            },
        })

        # 추가된 테이블별 이벤트
        for table in diff.added_tables:
            events.append({
                "event_type": "metadata.table.added",
                "tenant_id": tenant_id,
                "datasource_name": datasource_name,
                "actor": "system",
                "payload": {
                    "schema": table["schema"],
                    "table_name": table["name"],
                    "table_type": table.get("type", "BASE TABLE"),
                    "columns_count": table.get("columns_count", 0),
                    "row_count": table.get("row_count"),
                },
            })

        # 삭제된 테이블별 이벤트
        for table in diff.removed_tables:
            events.append({
                "event_type": "metadata.table.removed",
                "tenant_id": tenant_id,
                "datasource_name": datasource_name,
                "actor": "system",
                "payload": {
                    "schema": table["schema"],
                    "table_name": table["name"],
                    "had_queries": table.get("had_queries", False),
                    "affected_query_count": table.get("query_count", 0),
                },
            })

        # 변경된 컬럼별 이벤트
        for col_change in diff.modified_columns:
            events.append({
                "event_type": "metadata.column.modified",
                "tenant_id": tenant_id,
                "datasource_name": datasource_name,
                "actor": "system",
                "payload": col_change,
            })

        # 배치 발행
        await self.event_publisher.publish_batch(events)

        yield ProgressEvent(event="complete", data={...})
```

### 3.4 발행 보장

```
[결정] at-least-once 발행을 보장한다.
[구현] Neo4j 트랜잭션 커밋 후 Redis XADD를 실행한다.

순서:
  1. Neo4j에 메타데이터 변경 커밋 (성공)
  2. Redis Streams에 이벤트 XADD
     - 성공: 정상 흐름
     - 실패: 경고 로그 기록, 메타데이터 변경은 롤백하지 않음

[이유] Weaver는 Neo4j를 사용하므로 Core의 Event Outbox 패턴
      (PostgreSQL 트랜잭션 내 event_outbox INSERT)을 그대로 적용할 수 없다.
      Neo4j와 Redis 간 분산 트랜잭션은 과도한 복잡성이므로,
      Redis 장애 시 소비자가 reconciliation 엔드포인트로 복구하는 전략을 채택한다.

[경고] 이 설계에서 Redis 장애 시 이벤트가 유실될 수 있다.
      그러나 메타데이터 변경 자체는 Neo4j에 영속되므로,
      소비자가 full re-sync를 요청하면 최종 일관성(eventual consistency)이 보장된다.
```

---

## 4. 이벤트 소비 (Consumers)

### 4.1 Oracle 소비자

Oracle은 Neo4j에 :Table, :Column, :Query, :ValueMapping 노드를 관리한다. Weaver의 메타데이터 변경은 Oracle의 벡터 인덱스와 캐시된 쿼리에 직접 영향을 준다.

| Event | Oracle 반응 | 상세 |
|-------|-----------|------|
| `metadata.extracted` | 새 테이블/컬럼 벡터 인덱싱 | diff.tables_added의 각 테이블에 대해 description 벡터를 계산하여 table_vector, column_vector 인덱스에 추가 |
| `metadata.table.added` | 테이블 벡터 인덱싱 + Enum 캐시 부트스트랩 | 새 테이블의 :Table 노드에 벡터 생성, 카테고리 컬럼의 DISTINCT 값 캐싱 |
| `metadata.table.removed` | 관련 :Query 노드 soft-delete | 삭제된 테이블을 USES_TABLE로 참조하는 :Query 노드의 text_to_sql_is_valid=false 설정 |
| `metadata.column.modified` | 영향받는 :Query 노드 무효화 | 변경된 컬럼을 사용하는 :Query의 confidence 감소, 캐시 히트 시 재생성 유도 |
| `metadata.description.updated` | 해당 노드 벡터 재계산 | description이 변경되면 임베딩 벡터를 재계산하여 table_vector/column_vector 갱신 |
| `metadata.snapshot.restored` | 전체 datasource 벡터 재인덱싱 | 스냅샷 복원은 대규모 변경이므로 해당 datasource의 전체 :Table/:Column 벡터를 재계산 |
| `metadata.glossary.updated` | :Domain/:Synonym 노드 업데이트 (향후) | 비즈니스 도메인 용어를 Oracle의 NL2SQL 컨텍스트에 반영 |

```python
# Oracle 소비자 구현 (개념)
# services/oracle/app/events/metadata_consumer.py

class OracleMetadataConsumer:
    """Weaver 메타데이터 변경 이벤트를 소비하여
    Oracle의 벡터 인덱스와 쿼리 캐시를 갱신한다."""

    CONSUMER_GROUP = "oracle-consumer"
    CONSUMER_NAME = "oracle-metadata-worker-1"
    STREAM_KEY = "axiom:metadata_changes"

    HANDLED_EVENTS = {
        "metadata.extracted",
        "metadata.table.added",
        "metadata.table.removed",
        "metadata.column.modified",
        "metadata.description.updated",
        "metadata.snapshot.restored",
        "metadata.glossary.updated",
    }

    async def handle_event(self, event_type: str, data: dict):
        tenant_id = data["tenant_id"]
        datasource = data["datasource_name"]
        payload = json.loads(data["payload"])

        if event_type == "metadata.extracted":
            # diff 기반 증분 벡터 인덱싱
            diff = payload.get("diff", {})
            for table_name in diff.get("tables_added", []):
                await self.vector_indexer.index_table(
                    tenant_id, datasource, table_name
                )

        elif event_type == "metadata.table.removed":
            # 관련 :Query soft-delete
            await self.query_cache.invalidate_by_table(
                tenant_id, datasource, payload["table_name"]
            )

        elif event_type == "metadata.description.updated":
            # 벡터 재계산
            target = payload["target_type"]  # "table" or "column"
            if target == "table":
                await self.vector_indexer.reindex_table_vector(
                    tenant_id, datasource, payload["table_name"]
                )
            else:
                await self.vector_indexer.reindex_column_vector(
                    tenant_id, datasource,
                    payload["table_name"], payload["column_name"]
                )

        elif event_type == "metadata.snapshot.restored":
            # 전체 재인덱싱 (비동기 백그라운드 태스크)
            await self.vector_indexer.full_reindex(
                tenant_id, datasource
            )
```

### 4.2 Synapse 소비자

Synapse는 온톨로지-스키마 링크와 EventLogBinding을 관리한다.

| Event | Synapse 반응 | 상세 |
|-------|------------|------|
| `metadata.extracted` | 온톨로지-스키마 링크 검증 | 추출 결과에서 테이블 목록을 받아 기존 온톨로지 노드의 schema 링크가 유효한지 확인 |
| `metadata.table.removed` | EventLogBinding 검증 | source_table이 삭제된 테이블을 가리키는 EventLogBinding을 INVALID 표시 |
| `metadata.snapshot.restored` | 온톨로지-스키마 링크 재구성 | 복원된 메타데이터와 온톨로지 간 링크를 재검증, 깨진 링크 자동 복구 또는 경고 |
| `metadata.glossary.updated` | 온톨로지 용어 동기화 | 비즈니스 도메인 용어를 온톨로지의 4계층(Instance/Process/Resource/Measure) 노드 description에 반영 |

```python
# Synapse 소비자 구현 (개념)
# services/synapse/app/events/metadata_consumer.py

class SynapseMetadataConsumer:
    """Weaver 메타데이터 변경 이벤트를 소비하여
    온톨로지-스키마 링크의 일관성을 유지한다."""

    CONSUMER_GROUP = "synapse-consumer"
    CONSUMER_NAME = "synapse-metadata-worker-1"
    STREAM_KEY = "axiom:metadata_changes"

    HANDLED_EVENTS = {
        "metadata.extracted",
        "metadata.table.removed",
        "metadata.snapshot.restored",
        "metadata.glossary.updated",
    }

    async def handle_event(self, event_type: str, data: dict):
        tenant_id = data["tenant_id"]
        datasource = data["datasource_name"]
        payload = json.loads(data["payload"])

        if event_type == "metadata.table.removed":
            # EventLogBinding 유효성 검증
            table_name = payload["table_name"]
            bindings = await self.binding_store.find_by_source_table(
                tenant_id, datasource, table_name
            )
            for binding in bindings:
                await self.binding_store.mark_invalid(
                    binding.id,
                    reason=f"Source table '{table_name}' removed from datasource"
                )
                logger.warning(
                    f"EventLogBinding {binding.id} invalidated: "
                    f"source_table '{table_name}' no longer exists"
                )

        elif event_type == "metadata.snapshot.restored":
            # 온톨로지-스키마 링크 재검증
            await self.ontology_reconciler.reconcile(
                tenant_id, datasource
            )
```

### 4.3 Canvas SSE 브릿지

Canvas는 React 18 프론트엔드이므로 Redis Streams를 직접 소비할 수 없다. Core Gateway가 중간 브릿지 역할을 한다.

| Event | Canvas 반응 |
|-------|-----------|
| `metadata.extracted` | 메타데이터 브라우저 UI 새로고침, 추출 완료 토스트 알림 |
| `metadata.table.added` | 테이블 트리에 새 노드 추가 |
| `metadata.table.removed` | 테이블 트리에서 노드 제거, 관련 패널 닫기 |
| `metadata.column.modified` | 컬럼 상세 패널 갱신 |
| `metadata.description.updated` | 설명 필드 실시간 갱신 |
| `metadata.snapshot.created` | 스냅샷 목록 갱신, 생성 완료 토스트 |
| `metadata.snapshot.restored` | 전체 메타데이터 브라우저 리로드 |
| `metadata.tag.changed` | 태그 뱃지 갱신 |
| `metadata.glossary.updated` | 용어 사전 패널 갱신 |

```python
# Core Gateway SSE 브릿지 구현 (개념)
# services/core/app/events/metadata_sse_bridge.py

class MetadataSSEBridge:
    """axiom:metadata_changes 스트림을 구독하여
    연결된 Canvas 클라이언트에게 SSE로 전달한다.

    Core Gateway의 /api/v1/events/stream SSE 엔드포인트에 통합된다.
    """

    CONSUMER_GROUP = "canvas-bridge"
    CONSUMER_NAME = "canvas-bridge-1"
    STREAM_KEY = "axiom:metadata_changes"

    async def stream_to_sse(self, tenant_id: str):
        """특정 테넌트의 메타데이터 이벤트를 SSE로 스트리밍"""
        redis = await get_redis()

        try:
            await redis.xgroup_create(
                self.STREAM_KEY, self.CONSUMER_GROUP,
                id="0", mkstream=True
            )
        except Exception:
            pass  # 이미 존재

        while True:
            messages = await redis.xreadgroup(
                groupname=self.CONSUMER_GROUP,
                consumername=self.CONSUMER_NAME,
                streams={self.STREAM_KEY: ">"},
                count=10,
                block=5000,
            )

            for stream, entries in messages:
                for entry_id, data in entries:
                    # 테넌트 필터링
                    if data.get("tenant_id") == tenant_id:
                        yield {
                            "event": data["event_type"],
                            "data": json.dumps({
                                "event_id": data["event_id"],
                                "datasource_name": data["datasource_name"],
                                "timestamp": data["timestamp"],
                                "payload": json.loads(data["payload"]),
                            }),
                        }

                    await redis.xack(
                        self.STREAM_KEY, self.CONSUMER_GROUP, entry_id
                    )
```

Canvas React 클라이언트에서의 수신 패턴:

```typescript
// Canvas: useMetadataEvents.ts
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export function useMetadataEvents(datasourceName: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    const eventSource = new EventSource(
      `/api/v1/events/stream?token=${getAuthToken()}`
    );

    eventSource.addEventListener('metadata.extracted', (event) => {
      const data = JSON.parse(event.data);
      if (data.datasource_name === datasourceName) {
        // React Query 캐시 무효화 → 자동 리패치
        queryClient.invalidateQueries(['metadata', datasourceName]);
      }
    });

    eventSource.addEventListener('metadata.description.updated', (event) => {
      const data = JSON.parse(event.data);
      // 해당 테이블/컬럼 description 낙관적 업데이트
      queryClient.setQueryData(
        ['metadata', datasourceName, data.payload.table_name],
        (old: any) => ({
          ...old,
          description: data.payload.new_description,
        })
      );
    });

    eventSource.addEventListener('metadata.snapshot.restored', () => {
      // 전체 메타데이터 리로드
      queryClient.invalidateQueries(['metadata']);
    });

    return () => eventSource.close();
  }, [datasourceName, queryClient]);
}
```

### 4.4 Vision 소비자

Vision은 OLAP 큐브 정의를 관리하며, Mondrian XML에서 참조하는 fact/dim 테이블이 실제로 존재하는지 검증해야 한다.

| Event | Vision 반응 | 상세 |
|-------|-----------|------|
| `metadata.extracted` | OLAP 큐브 정의 검증 | fact/dim 테이블 존재 확인, 존재하지 않으면 큐브 상태를 INVALID으로 변경 |
| `metadata.table.removed` | 큐브 정의 무효화 | 삭제된 테이블이 큐브의 factTable 또는 dimension table이면 해당 큐브 INVALID 처리 |
| `metadata.glossary.updated` | 인라인 용어 사전 대체 (향후) | 큐브 차원/측도 설명에 비즈니스 도메인 용어 반영 |

```python
# Vision 소비자 구현 (개념)
# services/vision/app/events/metadata_consumer.py

class VisionMetadataConsumer:
    """Weaver 메타데이터 변경 이벤트를 소비하여
    OLAP 큐브 정의의 유효성을 검증한다."""

    CONSUMER_GROUP = "vision-consumer"
    CONSUMER_NAME = "vision-metadata-worker-1"
    STREAM_KEY = "axiom:metadata_changes"

    HANDLED_EVENTS = {
        "metadata.extracted",
        "metadata.table.removed",
        "metadata.glossary.updated",
    }

    async def handle_event(self, event_type: str, data: dict):
        tenant_id = data["tenant_id"]
        datasource = data["datasource_name"]
        payload = json.loads(data["payload"])

        if event_type == "metadata.table.removed":
            table_name = payload["table_name"]
            # 이 테이블을 참조하는 큐브 검색
            affected_cubes = await self.cube_store.find_by_table(
                tenant_id, table_name
            )
            for cube in affected_cubes:
                is_fact = cube.fact_table == table_name
                is_dim = any(
                    d.table == table_name for d in cube.dimensions
                )
                if is_fact or is_dim:
                    await self.cube_store.set_status(
                        cube.name, "INVALID",
                        reason=f"Referenced table '{table_name}' removed"
                    )
                    logger.warning(
                        f"Cube '{cube.name}' invalidated: "
                        f"{'fact' if is_fact else 'dimension'} table "
                        f"'{table_name}' removed"
                    )
```

---

## 5. Consumer Group 설정

### 5.1 Redis Consumer Group 초기화

시스템 시작 시 (또는 첫 소비 시) Consumer Group을 생성한다.

```bash
# Redis CLI 또는 초기화 스크립트

# Oracle consumer group
redis-cli XGROUP CREATE axiom:metadata_changes oracle-consumer $ MKSTREAM

# Synapse consumer group
redis-cli XGROUP CREATE axiom:metadata_changes synapse-consumer $ MKSTREAM

# Canvas SSE bridge consumer group
redis-cli XGROUP CREATE axiom:metadata_changes canvas-bridge $ MKSTREAM

# Vision consumer group
redis-cli XGROUP CREATE axiom:metadata_changes vision-consumer $ MKSTREAM
```

```python
# 각 서비스의 startup 시 Consumer Group 자동 생성 (기존 Axiom 패턴)
async def ensure_consumer_group(redis: Redis, stream: str, group: str):
    """Consumer Group이 없으면 생성. 이미 존재하면 무시."""
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info(f"Created consumer group '{group}' on stream '{stream}'")
    except Exception:
        pass  # BUSYGROUP: Consumer Group name already exists
```

### 5.2 XREADGROUP + XACK 소비 패턴

모든 소비자는 Core의 WatchCEPWorker와 동일한 패턴을 따른다 (ADR-004 준수).

```python
# 공통 소비 루프 패턴

class BaseMetadataConsumer:
    """메타데이터 이벤트 소비자 기반 클래스.

    Core의 BaseWorker 패턴을 따르되,
    axiom:metadata_changes 스트림에 특화된다.
    """

    STREAM_KEY = "axiom:metadata_changes"

    def __init__(self, redis: Redis, consumer_group: str, consumer_name: str):
        self.redis = redis
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self._running = True

    async def start(self):
        await ensure_consumer_group(
            self.redis, self.STREAM_KEY, self.consumer_group
        )

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.STREAM_KEY: ">"},
                    count=10,
                    block=5000,  # 5초 블로킹 대기
                )

                for stream, entries in messages:
                    for entry_id, data in entries:
                        event_type = data.get("event_type", "")

                        # 처리 대상 이벤트만 처리
                        if event_type in self.HANDLED_EVENTS:
                            try:
                                await self._process_with_idempotency(
                                    entry_id, event_type, data
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to process metadata event: "
                                    f"type={event_type} entry_id={entry_id} "
                                    f"error={e}"
                                )
                                # 재시도 카운트 확인
                                await self._handle_failure(
                                    entry_id, data, e
                                )

                        # ACK: 처리 완료 (또는 처리 대상 아닌 이벤트)
                        await self.redis.xack(
                            self.STREAM_KEY, self.consumer_group, entry_id
                        )

            except Exception as e:
                logger.error(f"Consumer loop error: {e}")
                await asyncio.sleep(1)

    async def _process_with_idempotency(
        self, entry_id: str, event_type: str, data: dict
    ):
        """멱등성 보장 래퍼.

        event_id 기반 중복 체크 (Core event-outbox.md 멱등성 패턴 준수).
        """
        event_id = data.get("event_id", entry_id)
        dedup_key = f"metadata:processed:{self.consumer_group}:{event_id}"

        is_new = await self.redis.set(
            dedup_key, "1", nx=True, ex=7 * 86400  # 7일 TTL
        )
        if not is_new:
            logger.debug(f"Skipping duplicate event: {event_id}")
            return

        try:
            await self.handle_event(event_type, data)
        except Exception:
            # 실패 시 중복 체크 키 삭제 (재처리 허용)
            await self.redis.delete(dedup_key)
            raise

    async def handle_event(self, event_type: str, data: dict):
        """하위 클래스에서 구현"""
        raise NotImplementedError
```

---

## 6. 실패 처리

### 6.1 발행 실패 (Weaver → Redis)

```
상황: Weaver가 Neo4j에 메타데이터를 저장했지만 Redis XADD가 실패

원인:
  - Redis 서버 다운
  - Redis 메모리 부족
  - 네트워크 일시 장애

처리:
  1. Weaver는 경고 로그를 남기고 정상 응답을 반환한다.
     (메타데이터 변경은 Neo4j에 이미 커밋됨)
  2. Redis 복구 후 소비자가 stale 상태를 감지하면
     reconciliation 엔드포인트를 호출한다.

[금지] Redis 장애를 이유로 메타데이터 변경을 롤백하지 않는다.
      메타데이터의 무결성(Neo4j)이 이벤트 전파보다 중요하다.
```

### 6.2 소비 실패 (Consumer 처리 오류)

```
상황: 소비자가 이벤트를 수신했지만 처리 중 오류 발생

원인:
  - Oracle: 벡터 인덱싱 중 OpenAI API 오류
  - Synapse: Neo4j 쿼리 타임아웃
  - Vision: 큐브 정의 파일 파싱 오류

처리 흐름:
  1. 처리 실패 → XACK 하지 않음 → Redis pending entries에 남음
  2. XPENDING으로 미처리 메시지 확인
  3. 최대 3회 재시도 (exponential backoff: 5초, 15초, 45초)
  4. 3회 실패 → Dead Letter Queue (axiom:metadata_changes_dlq)로 이동
```

```python
# 실패 처리 구현

class BaseMetadataConsumer:
    MAX_RETRIES = 3
    DLQ_STREAM = "axiom:metadata_changes_dlq"

    async def _handle_failure(
        self, entry_id: str, data: dict, error: Exception
    ):
        """실패한 이벤트의 재시도 또는 DLQ 이동"""
        # Pending 정보 조회
        pending = await self.redis.xpending_range(
            self.STREAM_KEY, self.consumer_group,
            min=entry_id, max=entry_id, count=1,
        )

        if pending:
            delivery_count = pending[0].get("times_delivered", 1)

            if delivery_count >= self.MAX_RETRIES:
                # DLQ로 이동
                await self.redis.xadd(self.DLQ_STREAM, {
                    **data,
                    "original_entry_id": entry_id,
                    "consumer_group": self.consumer_group,
                    "error": str(error),
                    "retries_exhausted": str(delivery_count),
                    "dlq_timestamp": datetime.now(timezone.utc).isoformat(),
                })
                # 원본 ACK (pending에서 제거)
                await self.redis.xack(
                    self.STREAM_KEY, self.consumer_group, entry_id
                )
                logger.error(
                    f"Moved to DLQ after {delivery_count} retries: "
                    f"entry_id={entry_id} error={error}"
                )
            else:
                # 재시도를 위해 ACK 하지 않음
                # XPENDING + XCLAIM으로 자동 재할당됨
                backoff = 5 * (3 ** (delivery_count - 1))  # 5, 15, 45초
                logger.warning(
                    f"Retry {delivery_count}/{self.MAX_RETRIES} "
                    f"for entry_id={entry_id}, backoff={backoff}s"
                )
```

### 6.3 Pending 메시지 자동 복구

5분 이상 ACK되지 않은 메시지를 자동으로 재할당한다 (Core event-outbox.md 패턴 준수).

```python
# 각 소비자 서비스에서 주기적으로 실행
async def recover_pending_metadata_events(
    redis: Redis, consumer_group: str, consumer_name: str
):
    """5분 이상 미확인 메타데이터 이벤트를 재할당"""
    pending = await redis.xpending_range(
        "axiom:metadata_changes",
        consumer_group,
        min="-",
        max="+",
        count=100,
    )

    reclaimed = 0
    for msg in pending:
        idle_time_ms = msg.get("time_since_delivered", 0)
        if idle_time_ms > 300_000:  # 5분 초과
            await redis.xclaim(
                "axiom:metadata_changes",
                consumer_group,
                consumer_name,
                min_idle_time=300_000,
                message_ids=[msg["message_id"]],
            )
            reclaimed += 1
            logger.warning(
                f"Reclaimed pending metadata event: "
                f"message_id={msg['message_id']} idle={idle_time_ms}ms"
            )

    if reclaimed > 0:
        logger.info(f"Reclaimed {reclaimed} pending metadata events")
```

### 6.4 Reconciliation (전체 재동기화)

소비자가 stale 상태를 의심할 때 (Redis 장애 복구 후, 소비자 장기 다운 후 등), 전체 재동기화를 요청할 수 있다.

| 소비자 | Reconciliation 엔드포인트 | 동작 |
|--------|------------------------|------|
| Oracle | `POST /api/v1/text2sql/meta/reindex?datasource_id={id}` | 해당 datasource의 전체 :Table/:Column 벡터 재인덱싱, 무효 :Query soft-delete |
| Synapse | `POST /api/v1/ontology/reconcile` | 온톨로지-스키마 링크 전체 재검증, 깨진 링크 복구 |
| Vision | `POST /api/v1/vision/cubes/validate` | 전체 큐브 정의의 fact/dim 테이블 존재 여부 재검증 |
| Canvas | 사용자 수동 새로고침 또는 F5 | React Query 캐시 전체 무효화 → Weaver API 재호출 |

```python
# Oracle reconciliation 엔드포인트 (개념)
# services/oracle/app/api/meta.py

@router.post("/text2sql/meta/reindex")
async def reindex_metadata(
    datasource_id: str,
    request: Request,
):
    """메타데이터 벡터 인덱스 전체 재구축.

    사용 시나리오:
    1. Redis 장애 후 복구 시 이벤트가 유실된 경우
    2. Oracle 서비스가 장기간 다운된 후 재시작한 경우
    3. 관리자가 수동으로 재인덱싱을 요청하는 경우
    """
    # 1. Weaver API에서 최신 메타데이터 조회
    metadata = await weaver_client.get_datasource_metadata(datasource_id)

    # 2. 기존 벡터 삭제
    await vector_store.delete_vectors_by_datasource(datasource_id)

    # 3. 전체 테이블/컬럼 벡터 재생성
    for schema in metadata["schemas"]:
        for table in schema["tables"]:
            await vector_indexer.index_table(datasource_id, table)

    # 4. 무효 Query 정리
    await query_cache.cleanup_invalid_queries(datasource_id)

    return {"status": "ok", "reindexed_tables": metadata["table_count"]}
```

---

## 7. 모니터링

### 7.1 메트릭

| 메트릭 | 수집 방법 | 알림 임계값 |
|--------|---------|-----------|
| 이벤트 발행 속도 (events/sec) | Weaver 애플리케이션 메트릭 | - (참조용) |
| Consumer lag (미소비 메시지 수) | `XINFO GROUPS axiom:metadata_changes` → `lag` 필드 | lag > 100 → 경고 |
| Pending 메시지 수 | `XPENDING axiom:metadata_changes {group}` | pending > 50 → 경고 |
| 처리 실패 횟수 | 소비자 애플리케이션 메트릭 | 5분 내 실패 > 10건 → 경고 |
| 평균 처리 시간 | 소비자 애플리케이션 메트릭 | p99 > 30초 → 경고 |
| DLQ 크기 | `XLEN axiom:metadata_changes_dlq` | size > 0 → 즉시 알림 |

### 7.2 Redis 모니터링 명령

```bash
# 스트림 전체 정보
redis-cli XINFO STREAM axiom:metadata_changes

# Consumer Group 상태 (lag 포함)
redis-cli XINFO GROUPS axiom:metadata_changes

# 특정 Consumer Group의 pending 메시지
redis-cli XPENDING axiom:metadata_changes oracle-consumer - + 10

# DLQ 크기
redis-cli XLEN axiom:metadata_changes_dlq

# DLQ 내용 확인 (최근 5건)
redis-cli XREVRANGE axiom:metadata_changes_dlq + - COUNT 5

# 스트림 크기
redis-cli XLEN axiom:metadata_changes
```

### 7.3 알림 규칙

```
[필수] Consumer lag > 100 → Slack 경고 알림
  원인: 소비자 처리 속도가 발행 속도를 따라가지 못함
  조치: 소비자 인스턴스 스케일 아웃 또는 처리 로직 최적화

[필수] DLQ size > 0 → Slack 즉시 알림 (CRITICAL)
  원인: 3회 재시도 후에도 처리 실패
  조치: DLQ 메시지 수동 검토, 원인 해결 후 재처리

[필수] Pending 메시지 > 50 (5분 이상 미처리) → Slack 경고 알림
  원인: 소비자 크래시 또는 무한 루프
  조치: 소비자 상태 확인, 필요 시 재시작. XCLAIM으로 다른 소비자에게 재할당

[권장] 이벤트 발행 후 소비 완료까지 평균 지연 > 10초 → 모니터링 대시보드 표시
  정상 범위: < 2초 (Redis Streams BLOCK 5000ms + 처리 시간)
```

---

## 8. 스트림 운영 설정

### 8.1 MAXLEN

```python
# axiom:metadata_changes 스트림 설정
STREAM_CONFIG = {
    "axiom:metadata_changes": {
        "maxlen": 50_000,           # 최대 5만 메시지 보존
        "approximate": True,        # ~50000 (성능 우선)
        "consumer_groups": [
            "oracle-consumer",
            "synapse-consumer",
            "canvas-bridge",
            "vision-consumer",
        ],
    },
    "axiom:metadata_changes_dlq": {
        "maxlen": 10_000,           # DLQ는 1만 건까지
        "approximate": True,
    },
}
```

### 8.2 메시지 보존 정책

```
[결정] 메타데이터 이벤트는 MAXLEN 50,000으로 제한한다.
[근거] 일 평균 메타데이터 변경 이벤트: ~100건 (추출 + 보강 + 수동 변경)
      50,000건 = 약 500일분. 충분한 보존 기간.
      메모리 사용: 이벤트당 ~500 bytes × 50,000 = ~25MB (Redis 관점에서 무시 가능)

[결정] DLQ는 MAXLEN 10,000으로 제한한다.
[근거] DLQ에 메시지가 쌓이면 즉시 알림이 발송되므로, 대량 축적은 없어야 한다.
```

---

## 9. 재평가 조건

| 조건 | 재평가 대상 |
|------|-----------|
| Consumer lag이 일상적으로 > 50 | 소비자 수평 확장 또는 이벤트 배치 처리 도입 |
| Redis 메모리 사용이 급증 | MAXLEN 감소 또는 이벤트 압축 |
| 메타데이터 변경 빈도 > 1,000건/일 | 이벤트 배치 발행 (개별 column.modified 대신 batch 이벤트) |
| Redis 장애로 인한 이벤트 유실이 반복 | Event Outbox 패턴 도입 (Neo4j 내 outbox 컬렉션 또는 PostgreSQL outbox) |
| 크로스 모듈 트랜잭션이 필요한 경우 | Saga 패턴 도입 (ADR-005: Saga 보상 트랜잭션 참조) |

---

## 10. 관련 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| 이벤트 드리븐 아키텍처 | `services/core/docs/01_architecture/event-driven.md` | Core의 Event Outbox + Redis Streams 전체 설계 |
| ADR-004: Redis Streams | `services/core/docs/99_decisions/ADR-004-redis-streams-event-bus.md` | Redis Streams 선택 근거 |
| Event Outbox 패턴 | `services/core/docs/06_data/event-outbox.md` | at-least-once 보장 패턴 |
| Worker 시스템 | `services/core/docs/03_backend/worker-system.md` | Consumer Group 기반 Worker 구조 |
| Neo4j 메타데이터 | `services/weaver/docs/03_backend/neo4j-metadata.md` | Neo4j 메타데이터 CRUD |
| 스키마 인트로스펙션 | `services/weaver/docs/03_backend/schema-introspection.md` | 메타데이터 추출 엔진 |
| LLM 보강 | `services/weaver/docs/05_llm/metadata-enrichment.md` | LLM 기반 설명 생성 |
| Oracle Neo4j 스키마 | `services/oracle/docs/06_data/neo4j-schema.md` | Oracle의 벡터 인덱스 구조 |
| Oracle 캐시 시스템 | `services/oracle/docs/03_backend/cache-system.md` | 쿼리 캐시와 값 매핑 |
| Synapse 인제스트 | `services/synapse/docs/03_backend/ontology-ingest.md` | Redis Streams 기반 자동 인제스트 |
| Vision OLAP 엔진 | `services/vision/docs/01_architecture/olap-engine.md` | 큐브 정의와 ETL |
| Gateway API | `services/core/docs/02_api/gateway-api.md` | SSE 라우팅 설정 |
| ADR-005: Saga | `services/core/docs/99_decisions/ADR-005-saga-compensation.md` | 보상 트랜잭션 |
