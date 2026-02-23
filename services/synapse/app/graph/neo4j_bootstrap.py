from neo4j.exceptions import Neo4jError
from app.core.neo4j_client import Neo4jClient
import structlog

logger = structlog.get_logger()

class Neo4jBootstrap:
    """
    Neo4j schema initialization and migration.
    Runs on service startup. All operations are idempotent (IF NOT EXISTS).
    """
    SCHEMA_VERSION = "2.0.0"

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
            "CREATE FULLTEXT INDEX ontology_fulltext IF NOT EXISTS FOR (n:Resource|Process|Measure|KPI) ON EACH [n.name, n.description]",
            "CREATE FULLTEXT INDEX schema_fulltext IF NOT EXISTS FOR (n:Table|Column) ON EACH [n.name, n.description]",
        ]
        await self._execute_batch(indexes, "fulltext_indexes")

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
