"""스냅샷 활성화 엔드포인트 단위 테스트.

SnapshotService.activate_snapshot() 및 API 엔드포인트를 테스트한다.
Neo4j 클라이언트와 OntologyService를 모킹하여 격리된 환경에서 실행.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.snapshot_service import SnapshotService


# ── 테스트 픽스처 ──────────────────────────────────────────────────


@pytest.fixture
def mock_neo4j():
    """Neo4j 클라이언트 목"""
    client = MagicMock()
    session = AsyncMock()
    session.run = AsyncMock()

    # context manager 패턴
    client.session.return_value.__aenter__ = AsyncMock(return_value=session)
    client.session.return_value.__aexit__ = AsyncMock(return_value=False)

    return client, session


@pytest.fixture
def mock_ontology():
    """OntologyService 목"""
    svc = MagicMock()
    svc._case_nodes = {}
    svc._case_relations = {}
    return svc


@pytest.fixture
def snapshot_service(mock_neo4j, mock_ontology):
    """SnapshotService 인스턴스"""
    client, _ = mock_neo4j
    return SnapshotService(client, mock_ontology)


# ── 스냅샷 데이터 ──────────────────────────────────────────────────


SAMPLE_SNAPSHOT_DATA = {
    "nodes": [
        {"id": "node-1", "name": "OEE", "layer": "kpi", "case_id": "case-1"},
        {"id": "node-2", "name": "Availability", "layer": "measure", "case_id": "case-1"},
    ],
    "relations": [
        {
            "id": "rel-1",
            "source": "node-1",
            "target": "node-2",
            "type": "DERIVED_FROM",
            "weight": 0.8,
        },
    ],
}


# ── 테스트 케이스 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_snapshot_loads_data(snapshot_service, mock_neo4j):
    """스냅샷 활성화 시 스냅샷 데이터를 올바르게 로드하는지 검증"""
    _, session = mock_neo4j

    # _load_snapshot_data 모킹
    snapshot_service._load_snapshot_data = AsyncMock(return_value=SAMPLE_SNAPSHOT_DATA)

    result = await snapshot_service.activate_snapshot(
        case_id="case-1",
        snapshot_id="snap-1",
    )

    # 스냅샷 데이터 로드 호출 확인
    snapshot_service._load_snapshot_data.assert_called_once_with("snap-1")

    # 결과 검증
    assert result["snapshot_id"] == "snap-1"
    assert result["case_id"] == "case-1"
    assert result["status"] == "activated"


@pytest.mark.asyncio
async def test_activate_snapshot_restores_nodes(snapshot_service, mock_neo4j):
    """스냅샷의 노드가 올바르게 복원되는지 검증"""
    _, session = mock_neo4j
    snapshot_service._load_snapshot_data = AsyncMock(return_value=SAMPLE_SNAPSHOT_DATA)

    result = await snapshot_service.activate_snapshot(
        case_id="case-1",
        snapshot_id="snap-1",
    )

    assert result["restored_nodes"] == 2
    assert result["restored_relations"] == 1


@pytest.mark.asyncio
async def test_activate_snapshot_clears_existing(snapshot_service, mock_neo4j):
    """활성화 전 기존 온톨로지가 삭제되는지 검증"""
    _, session = mock_neo4j
    snapshot_service._load_snapshot_data = AsyncMock(return_value=SAMPLE_SNAPSHOT_DATA)

    await snapshot_service.activate_snapshot(case_id="case-1", snapshot_id="snap-1")

    # DETACH DELETE 호출 확인 (첫 번째 session.run 호출)
    calls = session.run.call_args_list
    # 최소 1회의 DETACH DELETE 호출이 있어야 함
    delete_calls = [
        c for c in calls
        if "DETACH DELETE" in str(c)
    ]
    assert len(delete_calls) >= 1, "기존 노드 삭제 쿼리가 호출되어야 합니다"


@pytest.mark.asyncio
async def test_activate_snapshot_not_found(snapshot_service):
    """존재하지 않는 스냅샷 활성화 시 KeyError 발생"""
    snapshot_service._load_snapshot_data = AsyncMock(
        side_effect=KeyError("Snapshot snap-999 not found")
    )

    with pytest.raises(KeyError, match="snap-999"):
        await snapshot_service.activate_snapshot(
            case_id="case-1",
            snapshot_id="snap-999",
        )


@pytest.mark.asyncio
async def test_activate_snapshot_invalidates_cache(snapshot_service, mock_neo4j, mock_ontology):
    """활성화 후 인메모리 캐시가 무효화되는지 검증"""
    _, session = mock_neo4j
    snapshot_service._load_snapshot_data = AsyncMock(return_value=SAMPLE_SNAPSHOT_DATA)

    # 캐시에 데이터 추가
    mock_ontology._case_nodes["case-1"] = {"node-old": {}}
    mock_ontology._case_relations["case-1"] = {"rel-old": {}}

    await snapshot_service.activate_snapshot(case_id="case-1", snapshot_id="snap-1")

    # 캐시가 비어야 함
    assert "case-1" not in mock_ontology._case_nodes
    assert "case-1" not in mock_ontology._case_relations


@pytest.mark.asyncio
async def test_activate_snapshot_empty_data(snapshot_service, mock_neo4j):
    """빈 스냅샷 활성화도 정상 동작하는지 검증"""
    _, session = mock_neo4j
    snapshot_service._load_snapshot_data = AsyncMock(
        return_value={"nodes": [], "relations": []}
    )

    result = await snapshot_service.activate_snapshot(
        case_id="case-1",
        snapshot_id="snap-empty",
    )

    assert result["restored_nodes"] == 0
    assert result["restored_relations"] == 0
    assert result["status"] == "activated"


@pytest.mark.asyncio
async def test_activate_snapshot_marks_active_flag(snapshot_service, mock_neo4j):
    """스냅샷 활성 플래그가 올바르게 설정되는지 검증"""
    _, session = mock_neo4j
    snapshot_service._load_snapshot_data = AsyncMock(
        return_value={"nodes": [], "relations": []}
    )

    await snapshot_service.activate_snapshot(case_id="case-1", snapshot_id="snap-1")

    # is_active = true 설정 호출 확인
    calls = session.run.call_args_list
    activate_calls = [
        c for c in calls
        if "is_active = true" in str(c) or "is_active" in str(c)
    ]
    assert len(activate_calls) >= 1, "활성 플래그 설정 쿼리가 호출되어야 합니다"
