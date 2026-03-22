"""Sprint 3: 시멘틱 계약 Redis 캐시 + 이벤트 기반 무효화 테스트.

테스트 범위:
  - 캐시 적중 시 Synapse API 호출 없이 즉시 반환
  - 캐시 미적중 시 Synapse 호출 후 캐싱
  - 테넌트별 캐시 격리
  - 이벤트 수신 → 캐시 무효화
  - Redis 장애 시 graceful fallback
  - TTL 만료 시 재조회
  - 스냅샷 버전 계산 일관성
  - 직렬화/역직렬화 라운드트립
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.acl.synapse_acl import (
    OracleSynapseACL,
    SemanticContractContext,
    SemanticDimensionDef,
    SemanticJoinRule,
    SemanticMeasureDef,
)


# ---------------------------------------------------------------------------
# 헬퍼: 테스트용 시멘틱 계약 컨텍스트 팩토리
# ---------------------------------------------------------------------------

def _make_context(
    num_measures: int = 2,
    num_dimensions: int = 1,
    tenant_tag: str = "",
) -> SemanticContractContext:
    """테스트용 SemanticContractContext를 생성한다."""
    measures = [
        SemanticMeasureDef(
            measure_id=f"m{i}",
            name=f"measure_{i}{tenant_tag}",
            description=f"설명 {i}",
            measure_type="sum",
            sql_expression=f"SUM(col_{i})",
            filter_expression=None,
            additive_type="full",
            entity_id=f"entity_{i}",
            bound_concept_id=None,
        )
        for i in range(num_measures)
    ]
    dimensions = [
        SemanticDimensionDef(
            dimension_id=f"d{i}",
            name=f"dim_{i}",
            sql_expression=f"table.dim_{i}",
            value_type="string",
            hierarchy_path=None,
            entity_id=f"entity_0",
        )
        for i in range(num_dimensions)
    ]
    return SemanticContractContext(
        measures=measures,
        dimensions=dimensions,
        allowed_joins=[
            SemanticJoinRule(
                join_id="j1",
                left_entity_id="entity_0",
                right_entity_id="entity_1",
                join_type="LEFT",
                join_condition="a.id = b.fk",
                relationship_type="1:N",
                fanout_risk_score=0.2,
            ),
        ],
        synonym_map={"매출": "revenue"},
        concept_definitions={"c1": "매출액 정의"},
        entity_sources={"entity_0": "sales", "entity_1": "orders"},
        quality_warnings=["테스트 경고"],
        provenance="test_v1",
    )


# ---------------------------------------------------------------------------
# 헬퍼: Synapse API 응답을 모방한 dict (fetch_from_synapse용)
# ---------------------------------------------------------------------------

def _synapse_api_response(ctx: SemanticContractContext) -> dict:
    """ACL._fetch_from_synapse가 파싱할 수 있는 Synapse API 응답 형식."""
    return {
        "data": {
            "measures": [
                {
                    "measure_id": m.measure_id,
                    "name": m.name,
                    "description": m.description,
                    "measure_type": m.measure_type,
                    "sql_expression": m.sql_expression,
                    "filter_expression": m.filter_expression,
                    "additive_type": m.additive_type,
                    "entity_id": m.entity_id,
                    "bound_concept_id": m.bound_concept_id,
                }
                for m in ctx.measures
            ],
            "dimensions": [
                {
                    "dimension_id": d.dimension_id,
                    "name": d.name,
                    "sql_expression": d.sql_expression,
                    "value_type": d.value_type,
                    "hierarchy_path": d.hierarchy_path,
                    "entity_id": d.entity_id,
                }
                for d in ctx.dimensions
            ],
            "allowed_joins": [
                {
                    "join_id": j.join_id,
                    "left_entity_id": j.left_entity_id,
                    "right_entity_id": j.right_entity_id,
                    "join_type": j.join_type,
                    "join_condition": j.join_condition,
                    "relationship_type": j.relationship_type,
                    "fanout_risk_score": j.fanout_risk_score,
                }
                for j in ctx.allowed_joins
            ],
            "banned_joins": [],
            "entities": [
                {"entity_id": eid, "physical_source_ref": src}
                for eid, src in ctx.entity_sources.items()
            ],
            "concepts": [
                {"concept_id": cid, "business_definition": cdef}
                for cid, cdef in ctx.concept_definitions.items()
            ],
            "synonym_map": dict(ctx.synonym_map),
            "quality_contracts": [],
        }
    }


# ---------------------------------------------------------------------------
# Fake Redis: 인메모리 Redis 에뮬레이터
# ---------------------------------------------------------------------------

class FakeRedis:
    """테스트용 인메모리 Redis 에뮬레이터.

    get/set/delete/scan_iter만 구현한다.
    """

    def __init__(self):
        self._store: dict[str, tuple[bytes, float | None]] = {}

    async def get(self, key: str) -> bytes | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str | bytes, ex: int | None = None) -> None:
        raw = value.encode("utf-8") if isinstance(value, str) else value
        expires_at = (time.time() + ex) if ex else None
        self._store[key] = (raw, expires_at)

    async def delete(self, key: str) -> int:
        if key in self._store:
            del self._store[key]
            return 1
        return 0

    async def scan_iter(self, match: str = "*", count: int = 100):
        """간단한 glob 매칭 (와일드카드 * 만 지원)."""
        import fnmatch
        for key in list(self._store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    async def xread(self, streams: dict, block: int = 0, count: int = 10):
        """테스트용 XREAD 스텁 — 기본적으로 빈 리스트 반환."""
        return []


# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def acl(fake_redis: FakeRedis) -> OracleSynapseACL:
    """Redis가 주입된 ACL 인스턴스."""
    instance = OracleSynapseACL(
        base_url="http://synapse-test:8003",
        redis_client=fake_redis,
    )
    return instance


# ---------------------------------------------------------------------------
# 1. 캐시 적중 → Synapse API 호출 없이 즉시 반환
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_returns_cached_context(acl: OracleSynapseACL, fake_redis: FakeRedis):
    """캐시에 데이터가 있으면 Synapse API를 호출하지 않고 즉시 반환한다."""
    ctx = _make_context()
    # 미리 캐시에 저장
    cache_key = acl._cache_key("tenant1", None)
    serialized = acl._serialize_contract_context(ctx)
    await fake_redis.set(cache_key, json.dumps(serialized, ensure_ascii=False))

    # _fetch_from_synapse가 호출되지 않아야 함
    with patch.object(acl, "_fetch_from_synapse", new_callable=AsyncMock) as mock_fetch:
        result = await acl.fetch_semantic_contract_context("tenant1")

        mock_fetch.assert_not_called()
        assert result is not None
        assert len(result.measures) == 2
        assert result.measures[0].name == "measure_0"
        assert result.synonym_map == {"매출": "revenue"}


# ---------------------------------------------------------------------------
# 2. 캐시 미적중 → Synapse 호출 후 결과 캐싱
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_fetches_from_synapse(acl: OracleSynapseACL, fake_redis: FakeRedis):
    """캐시가 비어있으면 Synapse API를 호출하고 결과를 캐싱한다."""
    ctx = _make_context()
    api_resp = _synapse_api_response(ctx)

    with patch.object(acl, "_request_with_retry", new_callable=AsyncMock, return_value=api_resp):
        result = await acl.fetch_semantic_contract_context("tenant1")

    assert result is not None
    assert len(result.measures) == 2

    # 캐시에 저장되었는지 확인
    cache_key = acl._cache_key("tenant1", None)
    cached_raw = await fake_redis.get(cache_key)
    assert cached_raw is not None


# ---------------------------------------------------------------------------
# 3. 캐시 저장 확인 (fetch 후 set 호출)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_set_on_fetch(acl: OracleSynapseACL, fake_redis: FakeRedis):
    """Synapse에서 가져온 컨텍스트가 Redis에 정확히 직렬화되어 저장된다."""
    ctx = _make_context(num_measures=3)
    api_resp = _synapse_api_response(ctx)

    with patch.object(acl, "_request_with_retry", new_callable=AsyncMock, return_value=api_resp):
        await acl.fetch_semantic_contract_context("t2", case_id="case-abc")

    cache_key = acl._cache_key("t2", "case-abc")
    raw = await fake_redis.get(cache_key)
    assert raw is not None
    data = json.loads(raw)
    assert len(data["measures"]) == 3
    assert "cached_at" in data


# ---------------------------------------------------------------------------
# 4. 이벤트 수신 → 캐시 무효화
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_invalidation_on_event(acl: OracleSynapseACL, fake_redis: FakeRedis):
    """invalidate_cache 호출 시 해당 테넌트의 모든 캐시가 삭제된다."""
    ctx = _make_context()
    serialized = json.dumps(acl._serialize_contract_context(ctx), ensure_ascii=False)

    # 여러 케이스에 대한 캐시 생성
    await fake_redis.set(acl._cache_key("tenant1", None), serialized)
    await fake_redis.set(acl._cache_key("tenant1", "case-1"), serialized)
    await fake_redis.set(acl._cache_key("tenant2", None), serialized)

    # tenant1만 무효화
    deleted = await acl.invalidate_cache("tenant1")
    assert deleted == 2

    # tenant1 캐시 삭제 확인
    assert await fake_redis.get(acl._cache_key("tenant1", None)) is None
    assert await fake_redis.get(acl._cache_key("tenant1", "case-1")) is None

    # tenant2 캐시 유지 확인
    assert await fake_redis.get(acl._cache_key("tenant2", None)) is not None


# ---------------------------------------------------------------------------
# 5. TTL 만료 → 캐시 미적중 → 재조회
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_ttl_expiry(acl: OracleSynapseACL, fake_redis: FakeRedis):
    """TTL이 만료된 캐시는 None을 반환하여 Synapse를 재조회한다."""
    ctx = _make_context()
    cache_key = acl._cache_key("tenant1", None)

    # TTL 0초로 저장 → 즉시 만료
    serialized = json.dumps(acl._serialize_contract_context(ctx), ensure_ascii=False)
    # 직접 만료 시간을 과거로 설정
    fake_redis._store[cache_key] = (serialized.encode(), time.time() - 1)

    # 캐시 조회 → None (만료됨)
    cached = await acl._get_from_cache(cache_key)
    assert cached is None


# ---------------------------------------------------------------------------
# 6. Redis 장애 시 graceful fallback (Synapse 직접 호출)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_failure_fallback():
    """Redis가 없거나 장애 시에도 Synapse 직접 호출로 정상 동작한다."""
    # Redis 없이 ACL 생성
    acl_no_redis = OracleSynapseACL(base_url="http://synapse:8003")
    ctx = _make_context()
    api_resp = _synapse_api_response(ctx)

    with patch.object(acl_no_redis, "_request_with_retry", new_callable=AsyncMock, return_value=api_resp):
        result = await acl_no_redis.fetch_semantic_contract_context("tenant1")

    assert result is not None
    assert len(result.measures) == 2


@pytest.mark.asyncio
async def test_redis_error_during_get_graceful(acl: OracleSynapseACL):
    """Redis get 중 예외 발생 시 캐시 미적중으로 처리, Synapse 호출로 폴백."""
    # Redis get에서 예외 발생하도록 설정
    broken_redis = AsyncMock()
    broken_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    broken_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    broken_redis.scan_iter = MagicMock(return_value=AsyncMock())
    acl._redis = broken_redis

    ctx = _make_context()
    api_resp = _synapse_api_response(ctx)

    with patch.object(acl, "_request_with_retry", new_callable=AsyncMock, return_value=api_resp):
        result = await acl.fetch_semantic_contract_context("tenant1")

    # Redis 장애에도 Synapse 직접 호출로 결과를 얻어야 함
    assert result is not None
    assert len(result.measures) == 2


# ---------------------------------------------------------------------------
# 7. 멀티테넌트 캐시 격리
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_tenants_separate_cache(acl: OracleSynapseACL, fake_redis: FakeRedis):
    """서로 다른 테넌트의 캐시가 격리되어야 한다."""
    ctx_t1 = _make_context(num_measures=1, tenant_tag="_t1")
    ctx_t2 = _make_context(num_measures=3, tenant_tag="_t2")

    # 각 테넌트별 캐시 저장
    key_t1 = acl._cache_key("tenant1", None)
    key_t2 = acl._cache_key("tenant2", None)
    await fake_redis.set(key_t1, json.dumps(acl._serialize_contract_context(ctx_t1), ensure_ascii=False))
    await fake_redis.set(key_t2, json.dumps(acl._serialize_contract_context(ctx_t2), ensure_ascii=False))

    # 각각 올바른 컨텍스트를 반환하는지 확인
    with patch.object(acl, "_fetch_from_synapse", new_callable=AsyncMock) as mock_fetch:
        result_t1 = await acl.fetch_semantic_contract_context("tenant1")
        result_t2 = await acl.fetch_semantic_contract_context("tenant2")

        mock_fetch.assert_not_called()
        assert result_t1 is not None
        assert result_t2 is not None
        assert len(result_t1.measures) == 1
        assert len(result_t2.measures) == 3
        assert result_t1.measures[0].name == "measure_0_t1"
        assert result_t2.measures[0].name == "measure_0_t2"


# ---------------------------------------------------------------------------
# 8. 이벤트 리스너 메시지 처리
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_listener_processes_messages(fake_redis: FakeRedis):
    """이벤트 리스너가 XREAD 메시지를 처리하여 캐시를 무효화한다."""
    from app.main import _semantic_event_listener, _INVALIDATION_EVENT_TYPES

    acl = OracleSynapseACL(base_url="http://synapse:8003", redis_client=fake_redis)

    # 캐시 생성
    ctx = _make_context()
    serialized = json.dumps(acl._serialize_contract_context(ctx), ensure_ascii=False)
    await fake_redis.set(acl._cache_key("evt_tenant", None), serialized)

    # xread가 한 번은 메시지를 반환하고, 두 번째부터는 CancelledError로 루프 종료
    msg_id = b"1234567890-0"
    messages = [
        (
            b"axiom:synapse:events",
            [
                (msg_id, {
                    b"event_type": b"SEMANTIC_MEASURE_PUBLISHED",
                    b"tenant_id": b"evt_tenant",
                }),
            ],
        ),
    ]

    call_count = 0
    original_invalidate = acl.invalidate_cache

    async def fake_xread(streams, block=0, count=10):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return messages
        # 두 번째 호출에서 루프 종료
        raise asyncio.CancelledError()

    fake_redis.xread = fake_xread

    # ACL 싱글톤 대신 테스트 인스턴스 사용
    with patch("app.main.oracle_synapse_acl", acl):
        task = asyncio.create_task(_semantic_event_listener(fake_redis))
        # 이벤트 처리 완료 대기 (CancelledError로 종료)
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    # 캐시가 무효화되었는지 확인
    assert await fake_redis.get(acl._cache_key("evt_tenant", None)) is None


# ---------------------------------------------------------------------------
# 9. 직렬화/역직렬화 라운드트립
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serialize_deserialize_roundtrip():
    """SemanticContractContext의 직렬화→역직렬화가 원본과 동일해야 한다."""
    original = _make_context(num_measures=3, num_dimensions=2)

    serialized = OracleSynapseACL._serialize_contract_context(original)
    restored = OracleSynapseACL._deserialize_contract_context(serialized)

    # 핵심 필드 비교
    assert len(restored.measures) == len(original.measures)
    assert len(restored.dimensions) == len(original.dimensions)
    assert len(restored.allowed_joins) == len(original.allowed_joins)
    assert restored.synonym_map == original.synonym_map
    assert restored.concept_definitions == original.concept_definitions
    assert restored.entity_sources == original.entity_sources
    assert restored.quality_warnings == original.quality_warnings
    assert restored.provenance == original.provenance

    # 지표 상세 비교
    for orig, rest in zip(original.measures, restored.measures):
        assert orig.measure_id == rest.measure_id
        assert orig.name == rest.name
        assert orig.sql_expression == rest.sql_expression


# ---------------------------------------------------------------------------
# 10. 스냅샷 버전 계산 일관성
# ---------------------------------------------------------------------------

def test_snapshot_version_deterministic():
    """동일한 컨텍스트는 동일한 스냅샷 버전을 반환해야 한다."""
    ctx = _make_context()
    v1 = OracleSynapseACL._compute_snapshot_version("t1", ctx)
    v2 = OracleSynapseACL._compute_snapshot_version("t1", ctx)
    assert v1 == v2
    assert v1 is not None
    assert v1.startswith("sc_t1_")


def test_snapshot_version_differs_for_different_contexts():
    """다른 컨텍스트는 다른 스냅샷 버전을 반환해야 한다."""
    ctx1 = _make_context(num_measures=2)
    ctx2 = _make_context(num_measures=5)
    v1 = OracleSynapseACL._compute_snapshot_version("t1", ctx1)
    v2 = OracleSynapseACL._compute_snapshot_version("t1", ctx2)
    assert v1 != v2


def test_snapshot_version_none_for_none_context():
    """None 컨텍스트는 None 버전을 반환해야 한다."""
    assert OracleSynapseACL._compute_snapshot_version("t1", None) is None
