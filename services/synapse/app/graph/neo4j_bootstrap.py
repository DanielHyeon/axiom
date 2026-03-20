from neo4j.exceptions import Neo4jError
from app.core.neo4j_client import Neo4jClient
import structlog

logger = structlog.get_logger()

class Neo4jBootstrap:
    """
    Neo4j schema initialization and migration.
    Runs on service startup. All operations are idempotent (IF NOT EXISTS).
    """
    SCHEMA_VERSION = "2.3.0"

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    async def initialize(self):
        logger.info("neo4j_bootstrap_start", version=self.SCHEMA_VERSION)
        await self._check_connection()
        await self._create_legacy_constraints()
        await self._create_vector_indexes()
        await self._create_ontology_constraints()
        await self._create_ontology_indexes()
        await self._create_fulltext_indexes()
        await self._create_mapping_indexes()
        await self._create_snapshot_indexes()
        await self._create_kinetic_constraints()
        await self._record_schema_version()
        logger.info("neo4j_bootstrap_complete", version=self.SCHEMA_VERSION)

    async def _check_connection(self):
        async with self.neo4j.session() as session:
            result = await session.run("RETURN 1 AS check")
            record = await result.single()
            if record["check"] != 1:
                raise RuntimeError("Neo4j health check failed")
        logger.info("neo4j_connection_verified")

    async def _create_legacy_constraints(self):
        constraints = [
            "CREATE CONSTRAINT table_name_unique IF NOT EXISTS FOR (t:Table) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT column_composite_unique IF NOT EXISTS FOR (c:Column) REQUIRE (c.table_name, c.name) IS UNIQUE",
            "CREATE CONSTRAINT query_question_unique IF NOT EXISTS FOR (q:Query) REQUIRE q.question IS UNIQUE",
        ]
        await self._execute_batch(constraints, "legacy_constraints")

    async def _create_vector_indexes(self):
        indexes = [
            "CREATE VECTOR INDEX table_vector IF NOT EXISTS FOR (t:Table) ON (t.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}",
            "CREATE VECTOR INDEX column_vector IF NOT EXISTS FOR (c:Column) ON (c.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}",
            "CREATE VECTOR INDEX query_vector IF NOT EXISTS FOR (q:Query) ON (q.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}",
        ]
        await self._execute_batch(indexes, "vector_indexes")

    async def _create_ontology_constraints(self):
        layers = ["Resource", "Process", "Measure", "KPI"]
        constraints = []
        for layer in layers:
            constraints.append(f"CREATE CONSTRAINT {layer.lower()}_id_unique IF NOT EXISTS FOR (n:{layer}) REQUIRE n.id IS UNIQUE")
            constraints.append(f"CREATE CONSTRAINT {layer.lower()}_case_id IF NOT EXISTS FOR (n:{layer}) REQUIRE n.case_id IS NOT NULL")
        # Property-existence constraints require Neo4j Enterprise; skip on Community
        await self._execute_batch(constraints, "ontology_constraints", optional=True)

    async def _create_ontology_indexes(self):
        layers = ["Resource", "Process", "Measure", "KPI"]
        indexes = []
        for layer in layers:
            indexes.append(f"CREATE INDEX {layer.lower()}_case_type IF NOT EXISTS FOR (n:{layer}) ON (n.case_id, n.type)")
        indexes.append("CREATE INDEX resource_source IF NOT EXISTS FOR (r:Resource) ON (r.source)")
        indexes.append("CREATE INDEX resource_verified IF NOT EXISTS FOR (r:Resource) ON (r.case_id, r.verified)")
        await self._execute_batch(indexes, "ontology_indexes")

    async def _create_fulltext_indexes(self):
        indexes = [
            "CREATE FULLTEXT INDEX ontology_fulltext IF NOT EXISTS FOR (n:Resource|Process|Measure|KPI|Driver) ON EACH [n.name, n.description]",
            "CREATE FULLTEXT INDEX schema_fulltext IF NOT EXISTS FOR (n:Table|Column) ON EACH [n.name, n.description]",
        ]
        await self._execute_batch(indexes, "fulltext_indexes")

    async def _create_mapping_indexes(self):
        indexes = [
            "CREATE INDEX maps_to_index IF NOT EXISTS FOR ()-[r:MAPS_TO]-() ON (r.created_at)",
            "CREATE INDEX derived_from_index IF NOT EXISTS FOR ()-[r:DERIVED_FROM]-() ON (r.created_at)",
            "CREATE INDEX defines_index IF NOT EXISTS FOR ()-[r:DEFINES]-() ON (r.created_at)",
        ]
        await self._execute_batch(indexes, "mapping_indexes", optional=True)

    async def _create_snapshot_indexes(self):
        indexes = [
            "CREATE CONSTRAINT snapshot_id_unique IF NOT EXISTS FOR (s:OntologySnapshot) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX snapshot_case_id IF NOT EXISTS FOR (s:OntologySnapshot) ON (s.case_id)",
        ]
        await self._execute_batch(indexes, "snapshot_indexes", optional=True)

    async def _create_kinetic_constraints(self):
        """Kinetic Layer 노드(ActionType, Policy 등)에 대한 제약조건과 인덱스를 생성한다.

        Driver 라벨은 기존 온톨로지 5계층에서 누락되어 있었으므로 여기서 함께 추가한다.
        모든 구문은 IF NOT EXISTS이므로 멱등(idempotent)하게 동작한다.
        """
        kinetic_constraints = [
            # ── Driver (기존 온톨로지에서 누락된 라벨) ──
            # Driver 노드의 id는 중복될 수 없다
            "CREATE CONSTRAINT driver_id_unique IF NOT EXISTS FOR (d:Driver) REQUIRE d.id IS UNIQUE",
            # Driver 노드는 반드시 case_id를 가져야 한다
            "CREATE CONSTRAINT driver_case_id IF NOT EXISTS FOR (d:Driver) REQUIRE d.case_id IS NOT NULL",
            # Driver를 case_id + type으로 빠르게 검색하기 위한 복합 인덱스
            "CREATE INDEX driver_case_type IF NOT EXISTS FOR (d:Driver) ON (d.case_id, d.type)",

            # ── ActionType (GWT 룰을 저장하는 Kinetic Layer 노드) ──
            # ActionType 노드의 id는 중복될 수 없다
            "CREATE CONSTRAINT action_type_id_unique IF NOT EXISTS FOR (a:ActionType) REQUIRE a.id IS UNIQUE",
            # ActionType을 case_id로 빠르게 검색하기 위한 인덱스
            "CREATE INDEX action_type_case IF NOT EXISTS FOR (a:ActionType) ON (a.case_id)",
            # GWT Consumer가 when_event로 매칭할 때 사용하는 인덱스
            "CREATE INDEX action_type_event IF NOT EXISTS FOR (a:ActionType) ON (a.when_event)",

            # ── Policy (이벤트 반응형 자동 오케스트레이션 룰) ──
            # Policy 노드의 id는 중복될 수 없다
            "CREATE CONSTRAINT policy_id_unique IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE",
            # Policy를 case_id로 빠르게 검색하기 위한 인덱스
            "CREATE INDEX policy_case IF NOT EXISTS FOR (p:Policy) ON (p.case_id)",
            # PolicyExecutor가 trigger_event로 매칭할 때 사용하는 인덱스
            "CREATE INDEX policy_trigger IF NOT EXISTS FOR (p:Policy) ON (p.trigger_event)",

            # ── SimulationSnapshot (What-if 시뮬레이션 스냅샷) ──
            # SimulationSnapshot 노드의 id는 중복될 수 없다
            "CREATE CONSTRAINT sim_snapshot_id IF NOT EXISTS FOR (s:SimulationSnapshot) REQUIRE s.id IS UNIQUE",
            # SimulationSnapshot을 case_id로 빠르게 검색하기 위한 인덱스
            "CREATE INDEX sim_snapshot_case IF NOT EXISTS FOR (s:SimulationSnapshot) ON (s.case_id)",

            # ── Event (이벤트 프로젝션 노드) ──
            # Event를 case_id + type으로 빠르게 검색하기 위한 복합 인덱스
            "CREATE INDEX event_case_type IF NOT EXISTS FOR (e:Event) ON (e.case_id, e.type)",

            # ── DocFragment (문서 파이프라인 청크) ──
            # DocFragment 노드의 id는 중복될 수 없다
            "CREATE CONSTRAINT docfrag_id IF NOT EXISTS FOR (d:DocFragment) REQUIRE d.id IS UNIQUE",
            # DocFragment를 doc_id + page로 빠르게 검색하기 위한 복합 인덱스
            "CREATE INDEX docfrag_doc_page IF NOT EXISTS FOR (d:DocFragment) ON (d.doc_id, d.page)",
        ]
        # optional=True: Neo4j Community Edition에서 일부 제약조건이 지원되지 않을 수 있음
        await self._execute_batch(kinetic_constraints, "kinetic_constraints", optional=True)

    async def _record_schema_version(self):
        async with self.neo4j.session() as session:
            await session.run("MERGE (v:SchemaVersion {service: 'synapse'}) SET v.version = $version, v.updated_at = datetime()", version=self.SCHEMA_VERSION)

    async def _execute_batch(self, queries: list, batch_name: str, optional: bool = False):
        async with self.neo4j.session() as session:
            ok = 0
            for query in queries:
                try:
                    await session.run(query)
                    ok += 1
                except Neo4jError as e:
                    logger.error("schema_query_failed", batch=batch_name, query=query[:100], error=str(e))
                    if not optional:
                        raise
                except Exception as e:
                    logger.error("schema_query_failed", batch=batch_name, query=query[:100], error=str(e))
                    if not optional:
                        raise
        logger.info("schema_batch_complete", batch=batch_name, count=ok, total=len(queries))
