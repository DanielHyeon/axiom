# 자동 인제스트 파이프라인

## 이 문서가 답하는 질문

- 기존 케이스 데이터를 어떻게 온톨로지 노드로 자동 변환하는가?
- Redis Streams 이벤트 기반 인제스트는 어떻게 동작하는가?
- 인제스트 매핑 규칙은 무엇인가?
- 중복 생성을 어떻게 방지하는가?

<!-- affects: backend, data -->
<!-- requires-update: 06_data/ontology-model.md -->

---

## 1. 인제스트 개요

자동 인제스트는 Axiom Core의 PostgreSQL에 저장된 케이스 데이터가 변경될 때, Redis Streams 이벤트를 통해 Synapse가 감지하고 해당 데이터를 Neo4j 온톨로지 노드로 자동 변환하는 파이프라인이다.

```
PostgreSQL (케이스 데이터)
       │
       ▼ Core event_outbox
Redis Streams (case.* events)
       │
       ▼ Synapse Event Consumer
ontology_ingest.py
       │
       ▼ MERGE (upsert)
Neo4j (온톨로지 노드)
```

---

## 2. 이벤트 소비

### 2.1 구독 이벤트

| 이벤트 | 발행자 | 트리거 |
|--------|-------|--------|
| `case.created` | Core | 새 프로젝트 생성 |
| `case.updated` | Core | 프로젝트 정보 변경 |
| `case.process.started` | Core | 프로세스 단계 시작 |
| `case.process.completed` | Core | 프로세스 단계 완료 |
| `case.asset.registered` | Core | 자산 등록/평가 |
| `case.asset.disposed` | Core | 자산 처분 |
| `case.stakeholder.added` | Core | 이해관계자 추가 |
| `case.metric.updated` | Core | 지표 변경 |
| `case.financial.updated` | Core | 재무 정보 변경 |
| `case.process.advanced` | Core | 프로세스 단계 진행 |

### 2.2 이벤트 소비자 구현

```python
# app/events/consumer.py
import asyncio
import structlog
from app.core.redis_client import RedisStreamConsumer
from app.events.handlers import IngestEventHandler

logger = structlog.get_logger()


class SynapseEventConsumer:
    """
    Redis Streams consumer for case data change events.
    Triggers automatic ontology ingest pipeline.
    """

    STREAM_KEY = "axiom:events:case"
    CONSUMER_GROUP = "synapse-ingest"
    CONSUMER_NAME = "synapse-worker-1"

    def __init__(self, redis_client, handler: IngestEventHandler):
        self.redis = redis_client
        self.handler = handler

    async def start(self):
        """Start consuming events from Redis Streams"""
        # Ensure consumer group exists
        try:
            await self.redis.xgroup_create(
                self.STREAM_KEY, self.CONSUMER_GROUP, id="0", mkstream=True
            )
        except Exception:
            pass  # Group already exists

        logger.info("event_consumer_started", stream=self.STREAM_KEY)

        while True:
            try:
                events = await self.redis.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=self.CONSUMER_NAME,
                    streams={self.STREAM_KEY: ">"},
                    count=10,
                    block=5000  # 5 second block
                )

                for stream, messages in events:
                    for msg_id, data in messages:
                        await self._process_event(msg_id, data)
                        await self.redis.xack(
                            self.STREAM_KEY, self.CONSUMER_GROUP, msg_id
                        )

            except Exception as e:
                logger.error("event_consumer_error", error=str(e))
                await asyncio.sleep(5)  # Backoff on error

    async def _process_event(self, msg_id: str, data: dict):
        event_type = data.get("type")
        payload = data.get("payload")

        logger.info("event_received", event_type=event_type, msg_id=msg_id)

        try:
            await self.handler.handle(event_type, payload)
        except Exception as e:
            logger.error("event_processing_failed",
                         event_type=event_type, msg_id=msg_id, error=str(e))
            # Dead letter queue for failed events
            await self.redis.xadd(
                f"{self.STREAM_KEY}:dlq",
                {"original_id": msg_id, "error": str(e), **data}
            )
```

---

## 3. 인제스트 매핑 규칙

### 3.1 케이스 데이터 → 온톨로지 노드 매핑

| PostgreSQL 테이블 | 온톨로지 계층 | Neo4j 레이블 | 매핑 규칙 |
|------------------|------------|-----------|----------|
| `cases` | Process | `:DataCollection:Process` | case_type으로 분류 |
| `metrics` | Measure | `:Revenue:Measure` (집계) | 지표 유형별 집계 |
| `stakeholders` | Resource | `:Company:Resource` 또는 `:Person` | 이해관계자 유형으로 분류 |
| `assets` | Resource | `:Asset:Resource` | 자산 유형 매핑 |
| `financials` | Resource | `:Financial:Resource` | 재무 정보 |
| `kpi_results` | Measure | `:Throughput:Measure` | 성과 지표 |
| `case_processes` | Process | `:Process` (하위 유형) | 프로세스 단계별 생성 |

### 3.2 매핑 구현

```python
# app/events/handlers.py
class IngestEventHandler:
    """Maps case data events to ontology node MERGE operations"""

    MAPPING_RULES = {
        "case.created": "_ingest_case",
        "case.process.started": "_ingest_process",
        "case.asset.registered": "_ingest_asset",
        "case.stakeholder.added": "_ingest_stakeholder",
        "case.metric.updated": "_ingest_metric",
        "case.financial.updated": "_ingest_financial",
        "case.process.advanced": "_ingest_process_step",
    }

    async def handle(self, event_type: str, payload: dict):
        handler_name = self.MAPPING_RULES.get(event_type)
        if handler_name:
            handler = getattr(self, handler_name)
            await handler(payload)
        else:
            logger.warning("unknown_event_type", event_type=event_type)

    async def _ingest_case(self, payload: dict):
        """case.created -> DataCollection:Process node"""
        case_id = payload["case_id"]
        org_id = payload["org_id"]

        await self.ontology_ingest.merge_process_node(
            case_id=case_id,
            org_id=org_id,
            process_type="DataCollection",
            properties={
                "name": f"데이터 수집 - {payload.get('case_number', '')}",
                "department": payload.get("department"),
                "case_number": payload.get("case_number"),
                "start_date": payload.get("start_date"),
                "stage": "started",
            }
        )

        # Also create Company:Resource node for subject organization
        if payload.get("organization_name"):
            await self.ontology_ingest.merge_resource_node(
                case_id=case_id,
                org_id=org_id,
                resource_type="Company",
                properties={
                    "name": payload["organization_name"],
                    "registration_no": payload.get("registration_no"),
                    "industry": payload.get("industry"),
                }
            )

    async def _ingest_asset(self, payload: dict):
        """case.asset.registered -> Asset:Resource node"""
        await self.ontology_ingest.merge_resource_node(
            case_id=payload["case_id"],
            org_id=payload["org_id"],
            resource_type="Asset",
            properties={
                "name": payload["asset_name"],
                "type": payload["asset_type"],
                "market_value": payload.get("market_value"),
                "book_value": payload.get("book_value"),
                "appraised_date": payload.get("appraised_date"),
            }
        )
```

---

## 4. MERGE (Upsert) 패턴

### 4.1 기본 MERGE 패턴

```python
# app/graph/ontology_ingest.py
class OntologyIngest:
    """Handles automatic ontology node creation from case data events"""

    async def merge_resource_node(
        self, case_id: str, org_id: str, resource_type: str, properties: dict
    ) -> str:
        """
        Create or update a Resource node.
        Uses MERGE to prevent duplicates.
        Returns the node ID.
        """
        async with self.neo4j.session() as session:
            result = await session.execute_write(
                self._merge_resource_tx, case_id, org_id, resource_type, properties
            )
            return result

    @staticmethod
    async def _merge_resource_tx(tx, case_id, org_id, resource_type, properties):
        # Match key: case_id + type + name (unique within a case)
        query = f"""
        MERGE (n:{resource_type}:Resource {{
            case_id: $case_id,
            name: $name
        }})
        ON CREATE SET
            n.id = randomUUID(),
            n.org_id = $org_id,
            n.type = $resource_type,
            n.source = 'ingested',
            n.confidence = 1.0,
            n.verified = true,
            n.created_at = datetime(),
            n.updated_at = datetime()
        ON MATCH SET
            n.updated_at = datetime()
        SET n += $properties
        RETURN n.id AS node_id
        """

        result = await tx.run(query,
            case_id=case_id,
            org_id=org_id,
            name=properties["name"],
            resource_type=resource_type,
            properties={k: v for k, v in properties.items() if v is not None}
        )
        record = await result.single()
        return record["node_id"]
```

### 4.2 관계 자동 생성

노드 생성 후 관련 관계를 자동으로 생성한다.

```python
async def _create_auto_relations(self, case_id: str, node_id: str, node_layer: str):
    """
    Automatically create relations based on ontology rules:
    - Resource -> Process (PARTICIPATES_IN)
    - Process -> Measure (PRODUCES) - when measure data exists
    """
    if node_layer == "resource":
        # Link to all active processes in the same case
        await self._link_resource_to_processes(case_id, node_id)
    elif node_layer == "measure":
        # Link to producing process
        await self._link_measure_to_process(case_id, node_id)
        # Link to affected KPIs
        await self._link_measure_to_kpis(case_id, node_id)
```

### 4.3 KPI 자동 갱신

Measure 노드가 변경되면 관련 KPI를 자동으로 재계산한다.

```python
async def recalculate_kpi(self, case_id: str, kpi_type: str):
    """
    Recalculate KPI based on current Measure values.
    Example: ProcessEfficiency = Throughput / Cost
    """
    KPI_FORMULAS = {
        "ProcessEfficiency": """
            MATCH (m1:Throughput:Measure {case_id: $case_id})
            MATCH (m2:Cost:Measure {case_id: $case_id})
            MATCH (k:ProcessEfficiency:KPI {case_id: $case_id})
            SET k.actual = CASE WHEN m2.amount > 0 THEN m1.amount / m2.amount ELSE 0 END,
                k.updated_at = datetime()
            RETURN k
        """,
        "CycleTimeKPI": """
            MATCH (p:DataCollection:Process {case_id: $case_id})
            MATCH (k:CycleTimeKPI:KPI {case_id: $case_id})
            SET k.actual_months = duration.between(p.start_date, date()).months,
                k.updated_at = datetime()
            RETURN k
        """,
    }

    formula = KPI_FORMULAS.get(kpi_type)
    if formula:
        async with self.neo4j.session() as session:
            await session.run(formula, case_id=case_id)
```

---

## 5. 배치 인제스트

초기 마이그레이션이나 대량 데이터 적재 시 배치 인제스트를 사용한다.

```python
async def batch_ingest_case(self, case_id: str):
    """
    Full case ingest: read all case data from PostgreSQL
    and create ontology nodes in Neo4j.
    Used for initial setup or migration.
    """
    logger.info("batch_ingest_start", case_id=case_id)

    # 1. Ingest case (Process nodes)
    case_data = await self.pg_client.get_case(case_id)
    await self.merge_process_node(case_id, ...)

    # 2. Ingest stakeholders (Resource nodes)
    stakeholders = await self.pg_client.get_stakeholders(case_id)
    for stakeholder in stakeholders:
        await self.merge_resource_node(case_id, "Company", ...)

    # 3. Ingest assets (Resource nodes)
    assets = await self.pg_client.get_assets(case_id)
    for asset in assets:
        await self.merge_resource_node(case_id, "Asset", ...)

    # 4. Ingest metrics (Measure nodes - aggregated)
    metrics = await self.pg_client.get_metrics_summary(case_id)
    await self.merge_measure_node(case_id, "Revenue", ...)

    # 5. Create relations
    await self._create_auto_relations_batch(case_id)

    # 6. Initialize KPIs
    await self._initialize_kpis(case_id)

    logger.info("batch_ingest_complete", case_id=case_id)
```

---

## 6. 멱등성 보장

| 메커니즘 | 설명 |
|---------|------|
| **MERGE** | Neo4j MERGE로 동일 노드 중복 생성 방지 |
| **매치 키** | case_id + type + name 조합으로 유니크 매치 |
| **이벤트 ACK** | Redis XACK로 처리 완료 확인, 중복 소비 방지 |
| **DLQ** | 실패 이벤트를 Dead Letter Queue로 분리, 재처리 가능 |

---

## 금지 규칙

- CREATE를 사용하지 않는다 (항상 MERGE 사용)
- case_id 없이 노드를 생성하지 않는다
- 이벤트 처리 실패 시 예외를 무시하지 않는다 (DLQ로 보낸다)

## 필수 규칙

- 모든 인제스트 노드의 source는 'ingested'로 설정한다
- 인제스트 노드의 confidence는 1.0, verified는 true로 설정한다
- Measure 변경 시 관련 KPI를 자동 재계산한다

---

## 근거 문서

- `01_architecture/architecture-overview.md` (비동기 인제스트 흐름)
- `06_data/ontology-model.md` (온톨로지 데이터 모델)
- K-AIR 역설계 분석 보고서 섹션 4.11.5 (모듈 간 통신)
