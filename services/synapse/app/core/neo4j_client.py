from neo4j import AsyncGraphDatabase, AsyncDriver
import structlog
from app.core.config import settings

logger = structlog.get_logger()

class Neo4jClient:
    def __init__(self):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    async def close(self):
        await self.driver.close()

    def session(self):
        return self.driver.session()

neo4j_client = Neo4jClient()
