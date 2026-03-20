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

    # ── 편의 메서드: GWT Engine / Graph Projector 등에서 사용 ──

    async def execute_read(self, query: str, params: dict | None = None, timeout: float = 10.0) -> list[dict]:
        """읽기 트랜잭션 실행 — 결과를 dict 리스트로 반환한다.

        Neo4j 세션을 열고, 쿼리를 실행한 뒤, 각 레코드를 dict로 변환해 돌려준다.
        timeout은 향후 트랜잭션 타임아웃 설정에 사용할 수 있도록 예약된 파라미터이다.
        """
        async with self.driver.session() as session:
            result = await session.run(query, **(params or {}))
            # 모든 레코드를 dict로 변환해서 리스트로 모은다
            return [dict(record) async for record in result]

    async def execute_write(self, query: str, params: dict | None = None) -> list[dict]:
        """쓰기 트랜잭션 실행 — execute_write 트랜잭션 함수 패턴을 사용한다.

        Neo4j의 명시적 쓰기 트랜잭션 안에서 쿼리를 실행하므로,
        Causal Cluster 환경에서도 올바른 라우팅이 보장된다.
        """
        async with self.driver.session() as session:
            # 트랜잭션 함수: Neo4j 드라이버가 재시도 로직을 자동으로 처리한다
            async def _tx_work(tx):
                result = await tx.run(query, **(params or {}))
                return [dict(record) async for record in result]
            return await session.execute_write(_tx_work)

neo4j_client = Neo4jClient()
