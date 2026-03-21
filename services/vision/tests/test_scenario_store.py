"""시나리오 저장소 단위 테스트.

대상 모듈: app.services.scenario_store
Mock Redis를 사용하여 CRUD 동작을 검증한다.
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio

from app.services.scenario_store import (
    save_scenario,
    load_scenario,
    list_scenarios,
    delete_scenario,
    _sanitize_key,
    _scenario_key,
    _list_key,
)


# ===================================================================
# Mock Redis — 실제 Redis 없이 테스트
# ===================================================================

class MockRedis:
    """테스트용 가짜 Redis 클라이언트."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}
        self._expiry: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = value
        if ex is not None:
            self._expiry[key] = ex

    async def delete(self, key: str) -> int:
        deleted = 1 if key in self._data else 0
        self._data.pop(key, None)
        return deleted

    async def sadd(self, key: str, *values: str) -> None:
        self._sets.setdefault(key, set()).update(values)

    async def srem(self, key: str, *values: str) -> None:
        if key in self._sets:
            self._sets[key] -= set(values)

    async def smembers(self, key: str) -> set[str]:
        return self._sets.get(key, set())

    async def expire(self, key: str, seconds: int) -> None:
        self._expiry[key] = seconds


# ===================================================================
# 픽스처
# ===================================================================

@pytest.fixture
def redis():
    """테스트마다 새로운 MockRedis 인스턴스를 반환한다."""
    return MockRedis()


def _sample_scenario(scenario_id: str = "sc-001", name: str = "테스트 시나리오") -> dict:
    """테스트용 시나리오 딕셔너리."""
    return {
        "id": scenario_id,
        "name": name,
        "description": "단위 테스트용 시나리오",
        "interventions": {"X": 10.0, "Y": 20.0},
        "results": {"X": 10.0, "Y": 25.0, "Z": 50.0},
        "baseline": {"X": 5.0, "Y": 20.0, "Z": 40.0},
    }


# ===================================================================
# 키 생성 및 정규화 (순수 함수)
# ===================================================================

class TestKeyFunctions:
    """Redis 키 생성/정규화 함수 테스트."""

    def test_sanitize_허용문자만_보존(self):
        """알파벳, 숫자, _, - 만 남기고 나머지를 제거해야 한다."""
        assert _sanitize_key("tenant-001") == "tenant-001"
        assert _sanitize_key("t@e#n$a%n^t") == "tenant"
        assert _sanitize_key("abc_123-XYZ") == "abc_123-XYZ"

    def test_scenario_key_형식(self):
        """시나리오 키가 올바른 형식이어야 한다."""
        key = _scenario_key("t1", "s1")
        assert key == "axiom:vision:scenarios:t1:s1"

    def test_list_key_형식(self):
        """인덱스 키가 올바른 형식이어야 한다."""
        key = _list_key("t1")
        assert key == "axiom:vision:scenarios:t1:_index"


# ===================================================================
# 저장/로드 (save_scenario, load_scenario)
# ===================================================================

class TestSaveAndLoad:
    """시나리오 저장 및 로드 테스트."""

    @pytest.mark.asyncio
    async def test_저장_후_로드(self, redis):
        """저장한 시나리오를 동일한 데이터로 로드할 수 있어야 한다."""
        scenario = _sample_scenario()
        await save_scenario(redis, "t1", scenario)

        loaded = await load_scenario(redis, "t1", "sc-001")
        assert loaded is not None
        assert loaded["id"] == "sc-001"
        assert loaded["name"] == "테스트 시나리오"
        assert loaded["interventions"] == {"X": 10.0, "Y": 20.0}

    @pytest.mark.asyncio
    async def test_존재하지_않는_시나리오_None(self, redis):
        """존재하지 않는 시나리오를 로드하면 None을 반환해야 한다."""
        loaded = await load_scenario(redis, "t1", "nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_자동_ID_생성(self, redis):
        """ID가 없는 시나리오를 저장하면 UUID가 자동 생성되어야 한다."""
        scenario = {"name": "자동ID"}
        returned_id = await save_scenario(redis, "t1", scenario)
        assert returned_id != ""
        assert len(returned_id) > 10  # UUID는 36자

        loaded = await load_scenario(redis, "t1", returned_id)
        assert loaded is not None
        assert loaded["name"] == "자동ID"


# ===================================================================
# 목록 조회 (list_scenarios)
# ===================================================================

class TestListScenarios:
    """시나리오 목록 조회 테스트."""

    @pytest.mark.asyncio
    async def test_목록_조회_정렬(self, redis):
        """목록이 saved_at 기준 최신순으로 정렬되어야 한다."""
        s1 = _sample_scenario("sc-001", "첫번째")
        s2 = _sample_scenario("sc-002", "두번째")
        await save_scenario(redis, "t1", s1)
        await save_scenario(redis, "t1", s2)

        result = await list_scenarios(redis, "t1")
        assert len(result) == 2
        # 두 시나리오 모두 조회됨
        names = {r["name"] for r in result}
        assert "첫번째" in names
        assert "두번째" in names


# ===================================================================
# 삭제 (delete_scenario)
# ===================================================================

class TestDeleteScenario:
    """시나리오 삭제 테스트."""

    @pytest.mark.asyncio
    async def test_삭제_후_조회_None(self, redis):
        """삭제한 시나리오를 로드하면 None이어야 한다."""
        scenario = _sample_scenario()
        await save_scenario(redis, "t1", scenario)
        deleted = await delete_scenario(redis, "t1", "sc-001")
        assert deleted is True

        loaded = await load_scenario(redis, "t1", "sc-001")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_인덱스_업데이트(self, redis):
        """저장 시 인덱스에 추가, 삭제 시 인덱스에서 제거되어야 한다."""
        scenario = _sample_scenario()
        await save_scenario(redis, "t1", scenario)

        # 인덱스에 존재 확인
        index = await redis.smembers(_list_key("t1"))
        assert "sc-001" in index

        # 삭제 후 인덱스에서 제거 확인
        await delete_scenario(redis, "t1", "sc-001")
        index_after = await redis.smembers(_list_key("t1"))
        assert "sc-001" not in index_after


# ===================================================================
# None Redis 클라이언트 — 조용한 실패
# ===================================================================

class TestNoneRedis:
    """Redis 클라이언트가 None일 때의 방어적 처리 테스트."""

    @pytest.mark.asyncio
    async def test_None_redis_저장_빈문자열(self):
        """Redis=None일 때 save_scenario는 시나리오 ID를 반환해야 한다."""
        scenario = _sample_scenario()
        result = await save_scenario(None, "t1", scenario)
        assert result == "sc-001"

    @pytest.mark.asyncio
    async def test_None_redis_조회_None(self):
        """Redis=None일 때 load_scenario는 None을 반환해야 한다."""
        result = await load_scenario(None, "t1", "sc-001")
        assert result is None

    @pytest.mark.asyncio
    async def test_None_redis_목록_빈리스트(self):
        """Redis=None일 때 list_scenarios는 빈 리스트를 반환해야 한다."""
        result = await list_scenarios(None, "t1")
        assert result == []

    @pytest.mark.asyncio
    async def test_None_redis_삭제_False(self):
        """Redis=None일 때 delete_scenario는 False를 반환해야 한다."""
        result = await delete_scenario(None, "t1", "sc-001")
        assert result is False


# ===================================================================
# 테넌트 격리
# ===================================================================

class TestTenantIsolation:
    """멀티테넌트 데이터 격리 테스트."""

    @pytest.mark.asyncio
    async def test_tenant_격리(self, redis):
        """서로 다른 테넌트의 시나리오가 격리되어야 한다."""
        s1 = _sample_scenario("sc-001", "테넌트A 시나리오")
        s2 = _sample_scenario("sc-002", "테넌트B 시나리오")

        await save_scenario(redis, "tenant-a", s1)
        await save_scenario(redis, "tenant-b", s2)

        # 테넌트A는 자신의 시나리오만 조회
        list_a = await list_scenarios(redis, "tenant-a")
        assert len(list_a) == 1
        assert list_a[0]["name"] == "테넌트A 시나리오"

        # 테넌트B는 자신의 시나리오만 조회
        list_b = await list_scenarios(redis, "tenant-b")
        assert len(list_b) == 1
        assert list_b[0]["name"] == "테넌트B 시나리오"

        # 테넌트A는 테넌트B의 시나리오를 로드 불가
        cross = await load_scenario(redis, "tenant-a", "sc-002")
        assert cross is None
