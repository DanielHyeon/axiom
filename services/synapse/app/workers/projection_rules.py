"""
GraphProjector 이벤트→Cypher 매핑 정의 (Projection Rules)

각 이벤트 타입에 대해 Neo4j 온톨로지 그래프에 어떤 변경을 적용할지 선언적으로 정의한다.
CQRS Read-side Projection의 그래프 버전이며, 이벤트가 발생할 때마다
온톨로지를 "살아있는 디지털 트윈"으로 갱신하는 핵심 매핑 테이블이다.

구조:
  PROJECTION_RULES[이벤트_타입] = [
      {
          "description": "사람이 읽을 수 있는 규칙 설명",
          "cypher":      "실행할 Cypher 쿼리 (파라미터는 $변수명 형태)",
          "params_map":  {
              "cypher_파라미터명": "payload.필드명" | "$event_id" | "$full_payload"
          }
      },
      ...
  ]

params_map 해석 규칙:
  - "payload.xxx"   → 이벤트 payload dict에서 xxx 키를 가져온다
  - "$event_id"     → 이벤트 고유 ID를 사용한다
  - "$full_payload" → payload 전체를 JSON 문자열로 직렬화한다
  - 그 외 문자열    → 리터럴 값으로 사용한다

$case_id는 모든 규칙에 자동 주입되므로 params_map에 별도로 정의하지 않아도 된다.
"""

# ──────────────────────────────────────────────────────────────
# 이벤트 타입별 프로젝션 규칙
# ──────────────────────────────────────────────────────────────

PROJECTION_RULES: dict[str, list[dict]] = {

    # ================================================================
    # Core 서비스 이벤트
    # ================================================================

    "PROCESS_INITIATED": [
        {
            # 프로세스가 시작되면 해당 Process 노드의 상태를 RUNNING으로 변경한다.
            # case_id + process_node_id 조합으로 정확한 노드를 매칭한다.
            "description": "프로세스 시작 → Process 노드 상태를 RUNNING으로 업데이트",
            "cypher": """
                MATCH (p:Process {case_id: $case_id, node_id: $process_node_id})
                SET p.status = 'RUNNING',
                    p.started_at = datetime(),
                    p.updated_at = datetime()
            """,
            "params_map": {
                "process_node_id": "payload.process_node_id",
            },
        },
        {
            # 프로세스 시작 이벤트 자체를 Event 노드로 기록하고,
            # 해당 Process 노드와 HAS_EVENT 관계로 연결한다.
            # 이를 통해 프로세스의 이벤트 히스토리를 그래프에서 추적할 수 있다.
            "description": "프로세스 이벤트 노드 생성 + Process와 HAS_EVENT 관계 연결",
            "cypher": """
                MATCH (p:Process {case_id: $case_id, node_id: $process_node_id})
                CREATE (e:Event {
                    id: $event_id,
                    type: 'PROCESS_INITIATED',
                    case_id: $case_id,
                    timestamp: datetime(),
                    payload: $payload_json
                })
                CREATE (p)-[:HAS_EVENT]->(e)
            """,
            "params_map": {
                "process_node_id": "payload.process_node_id",
                "payload_json": "$full_payload",
            },
        },
    ],

    "WORKITEM_COMPLETED": [
        {
            # 작업 항목이 완료되면 담당 Resource와 Process 사이의 USES 관계
            # 가중치를 점진적으로 증가시킨다 (최대 1.0).
            # 가중치가 없으면 기본값 0.5에서 시작한다.
            # 이를 통해 어떤 리소스가 어떤 프로세스에 얼마나 기여하는지 자동으로 학습된다.
            "description": "작업 완료 → Resource-Process 관계 가중치 0.05 증가 (최대 1.0)",
            "cypher": """
                MATCH (r:Resource {case_id: $case_id, node_id: $resource_id})
                      -[rel:USES]->(p:Process {case_id: $case_id})
                SET rel.weight = CASE
                    WHEN rel.weight IS NULL THEN 0.5
                    ELSE min(1.0, rel.weight + 0.05)
                  END,
                    rel.last_activity = datetime(),
                    rel.updated_at = datetime()
            """,
            "params_map": {
                "resource_id": "payload.assignee_id",
            },
        },
    ],

    # ================================================================
    # Vision 서비스 이벤트
    # ================================================================

    "WHATIF_SIMULATION_COMPLETED": [
        {
            # What-If 시뮬레이션이 완료되면 결과를 SimulationSnapshot 노드로 생성한다.
            # 시나리오 이름, 수렴 여부, 전파 웨이브 수 등 핵심 메타데이터를 저장한다.
            # event_id를 snapshot_id로 재사용하여 이벤트↔스냅샷 간 추적이 가능하다.
            "description": "시뮬레이션 완료 → SimulationSnapshot 결과 노드 생성",
            "cypher": """
                CREATE (s:SimulationSnapshot {
                    id: $snapshot_id,
                    case_id: $case_id,
                    scenario_name: $scenario_name,
                    simulation_id: $simulation_id,
                    converged: $converged,
                    propagation_waves: $waves,
                    created_at: datetime()
                })
            """,
            "params_map": {
                "snapshot_id": "$event_id",
                "scenario_name": "payload.scenario_name",
                "simulation_id": "payload.simulation_id",
                "converged": "payload.converged",
                "waves": "payload.propagation_waves",
            },
        },
    ],

    "CAUSAL_RELATION_DISCOVERED": [
        {
            # 인과 분석(Granger/VAR)에서 새로운 인과 관계가 발견되면,
            # Driver 노드를 자동 생성(MERGE)하고 대상 노드와 CAUSES 관계를 만든다.
            # MERGE를 사용하므로 동일 driver_id가 이미 있으면 관계만 업데이트된다.
            # source='auto-discovered'로 표시하여 사람이 수동 생성한 것과 구분한다.
            "description": "인과 관계 발견 → Driver 노드 MERGE + CAUSES 관계 생성/업데이트",
            "cypher": """
                MERGE (d:Driver {case_id: $case_id, node_id: $driver_id})
                ON CREATE SET
                    d.name = $driver_name,
                    d.description = $description,
                    d.source = 'auto-discovered',
                    d.verified = false,
                    d.created_at = datetime()
                WITH d
                MATCH (target {case_id: $case_id, node_id: $target_node_id})
                MERGE (d)-[r:CAUSES]->(target)
                SET r.weight = $weight,
                    r.lag = $lag,
                    r.confidence = $confidence,
                    r.method = $method,
                    r.direction = $direction,
                    r.updated_at = datetime()
            """,
            "params_map": {
                "driver_id": "payload.driver_node_id",
                "driver_name": "payload.driver_name",
                "description": "payload.description",
                "target_node_id": "payload.target_node_id",
                "weight": "payload.weight",
                "lag": "payload.lag",
                "confidence": "payload.confidence",
                "method": "payload.method",
                "direction": "payload.direction",
            },
        },
    ],

    # ================================================================
    # Weaver 서비스 이벤트
    # ================================================================

    "INSIGHT_JOB_COMPLETED": [
        {
            # 인사이트 잡이 완료되면 해당 KPI 노드의 최신 값을 업데이트한다.
            # latest_value와 trend를 갱신하여 온톨로지 그래프가
            # 항상 최신 KPI 상태를 반영하도록 한다.
            "description": "인사이트 잡 완료 → KPI 노드의 latest_value 및 trend 업데이트",
            "cypher": """
                MATCH (k:Kpi {case_id: $case_id, node_id: $kpi_node_id})
                SET k.latest_value = $value,
                    k.latest_timestamp = datetime(),
                    k.trend = $trend,
                    k.updated_at = datetime()
            """,
            "params_map": {
                "kpi_node_id": "payload.kpi_node_id",
                "value": "payload.result_value",
                "trend": "payload.trend",
            },
        },
    ],

    "METADATA_TABLE_DISCOVERED": [
        {
            # Weaver가 데이터소스 인트로스펙션 중 새 테이블을 발견하면
            # Table 노드를 MERGE(없으면 생성, 있으면 업데이트)한다.
            # datasource_id로 스코핑하여 서로 다른 데이터소스의
            # 동명 테이블이 충돌하지 않도록 보장한다.
            "description": "새 테이블 발견 → Table 노드 MERGE (datasource_id 스코핑)",
            "cypher": """
                MERGE (t:Table {name: $table_name, datasource_id: $datasource_id})
                ON CREATE SET
                    t.schema = $schema_name,
                    t.datasource_id = $datasource_id,
                    t.description = $description,
                    t.row_count = $row_count,
                    t.created_at = datetime()
                ON MATCH SET
                    t.row_count = $row_count,
                    t.updated_at = datetime()
            """,
            "params_map": {
                "table_name": "payload.table_name",
                "schema_name": "payload.schema_name",
                "datasource_id": "payload.datasource_id",
                "description": "payload.description",
                "row_count": "payload.row_count",
            },
        },
    ],
}
