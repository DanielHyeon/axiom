"""
Synapse 단위 테스트 공통 fixture.

Neo4j 클라이언트를 더미로 교체하여 이벤트 루프 불일치 및
외부 Neo4j 인스턴스의 잔존 데이터로 인한 테스트 오염을 방지한다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


class _DummyNeo4jClient:
    """
    단위 테스트용 Neo4j 클라이언트 더미.

    session()을 호출하면 항상 예외를 발생시켜,
    OntologyService가 인메모리 폴백 경로를 사용하도록 강제한다.
    _run_neo4j_query는 이미 모든 예외를 catch하고 경고만 남기므로
    쓰기 경로는 안전하게 no-op이 된다.
    읽기 경로(_load_model_graph_from_neo4j)도 예외를 받아 인메모리 폴백으로 전환된다.
    """

    def session(self):
        raise ConnectionError("Unit test: Neo4j 연결 비활성화")

    async def close(self):
        pass

    async def execute_read(self, query, params=None, timeout=10.0):
        raise ConnectionError("Unit test: Neo4j 연결 비활성화")

    async def execute_write(self, query, params=None):
        raise ConnectionError("Unit test: Neo4j 연결 비활성화")


@pytest.fixture(autouse=True)
def _patch_neo4j_client(monkeypatch):
    """
    모든 단위 테스트에서 Neo4j 클라이언트를 더미로 교체.

    ontology_service와 graph_search_service 모두 패치하여
    CI 환경(Neo4j 미실행)에서도 안전하게 인메모리 폴백을 사용한다.
    autouse=True이므로 개별 테스트에서 별도 설정이 필요 없다.
    """
    from app.api.ontology import ontology_service
    monkeypatch.setattr(ontology_service, "_neo4j", _DummyNeo4jClient())

    # graph_search_service도 동일하게 더미로 교체 — Neo4j 없이 구조 검증 가능
    from app.services.graph_search_service import graph_search_service
    monkeypatch.setattr(graph_search_service, "_neo4j", _DummyNeo4jClient())
