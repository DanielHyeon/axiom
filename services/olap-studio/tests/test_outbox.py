"""OLAP Studio Transactional Outbox 단위 테스트.

대상 모듈: app.events.outbox
asyncpg 풀과 Redis를 모킹하여 순수 로직만 검증한다.
DB/Redis 없이 실행 가능.
"""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.events.outbox import (
    STREAM_KEY,
    MAX_RETRY,
    OlapRelayWorker,
    publish_event,
)


# ──────────────────────────────────────────────
# Mock DB Pool / Connection
# ──────────────────────────────────────────────

class MockConnection:
    """asyncpg Connection을 모방하는 가짜 커넥션."""

    def __init__(self):
        self.executed: list[tuple[str, str, tuple]] = []

    async def execute(self, sql: str, *args):
        self.executed.append(("execute", sql, args))
        return "INSERT 0 1"

    async def fetch(self, sql: str, *args):
        self.executed.append(("fetch", sql, args))
        return []


class MockPool:
    """asyncpg Pool을 모방하는 가짜 풀."""

    def __init__(self):
        self._conn = MockConnection()

    def acquire(self):
        return _MockAcquire(self._conn)


class _MockAcquire:
    """pool.acquire() 컨텍스트 매니저를 모방."""

    def __init__(self, conn: MockConnection):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


# ──────────────────────────────────────────────
# 테스트: 상수 검증
# ──────────────────────────────────────────────

class TestOutboxConstants:
    """Outbox 모듈의 상수 값을 검증한다."""

    def test_스트림_키_상수(self):
        """STREAM_KEY는 'axiom:olap-studio:events' 이어야 한다."""
        assert STREAM_KEY == "axiom:olap-studio:events"

    def test_최대_재시도_상수(self):
        """MAX_RETRY는 3이어야 한다."""
        assert MAX_RETRY == 3


# ──────────────────────────────────────────────
# 테스트: publish_event — Outbox INSERT
# ──────────────────────────────────────────────

class TestPublishEvent:
    """publish_event 함수의 DB INSERT 동작을 검증한다."""

    @pytest.mark.asyncio
    async def test_이벤트_발행_DB_INSERT(self):
        """publish_event는 outbox 테이블에 INSERT 문을 실행해야 한다."""
        conn = MockConnection()
        event_id = await publish_event(
            tenant_id="t-001",
            project_id="p-001",
            aggregate_type="Cube",
            aggregate_id="cube-001",
            event_type="CUBE_CREATED",
            payload={"name": "매출분석"},
            conn=conn,
        )
        # event_id가 UUID 문자열로 반환되어야 함
        assert isinstance(event_id, str)
        assert len(event_id) == 36  # UUID 형식: 8-4-4-4-12

        # INSERT가 1회 실행되어야 함
        assert len(conn.executed) == 1
        op, sql, args = conn.executed[0]
        assert op == "execute"
        assert "INSERT INTO olap.outbox_events" in sql

    @pytest.mark.asyncio
    async def test_이벤트_발행_필드_포함(self):
        """INSERT 파라미터에 tenant_id, project_id, event_type이 포함되어야 한다."""
        conn = MockConnection()
        await publish_event(
            tenant_id="t-002",
            project_id="p-002",
            aggregate_type="Query",
            aggregate_id="q-001",
            event_type="QUERY_EXECUTED",
            payload={"sql": "SELECT 1"},
            conn=conn,
        )
        _, _sql, args = conn.executed[0]
        # args: (event_id, event_type, aggregate_type, aggregate_id, tenant_id, project_id, payload_json)
        assert args[1] == "QUERY_EXECUTED"       # event_type
        assert args[2] == "Query"                 # aggregate_type
        assert args[3] == "q-001"                 # aggregate_id
        assert args[4] == "t-002"                 # tenant_id
        assert args[5] == "p-002"                 # project_id

    @pytest.mark.asyncio
    async def test_이벤트_발행_JSON_페이로드(self):
        """payload는 JSON 문자열로 직렬화되어 전달되어야 한다."""
        conn = MockConnection()
        payload = {"name": "매출분석", "dimensions": ["region", "date"]}
        await publish_event(
            tenant_id="t-003",
            project_id="p-003",
            aggregate_type="Cube",
            aggregate_id="cube-002",
            event_type="CUBE_UPDATED",
            payload=payload,
            conn=conn,
        )
        _, _sql, args = conn.executed[0]
        payload_json = args[6]
        # JSON으로 파싱 가능해야 함
        parsed = json.loads(payload_json)
        assert parsed["name"] == "매출분석"
        assert "region" in parsed["dimensions"]

    @pytest.mark.asyncio
    async def test_이벤트_발행_conn_없으면_풀에서_획득(self):
        """conn이 None이면 get_pool()로 독립 커넥션을 획득해야 한다."""
        mock_pool = MockPool()

        # get_pool은 함수 내부에서 from app.core.database import get_pool로 가져오므로
        # 원본 모듈을 패치해야 한다
        with patch("app.core.database.get_pool", new_callable=AsyncMock, return_value=mock_pool):
            event_id = await publish_event(
                tenant_id="t-004",
                project_id="p-004",
                aggregate_type="Cube",
                aggregate_id="cube-003",
                event_type="CUBE_DELETED",
                payload={"reason": "테스트 삭제"},
                conn=None,  # conn 미전달 -- 풀에서 가져옴
            )
        assert isinstance(event_id, str)
        # 풀의 내부 커넥션에서 실행되어야 함
        assert len(mock_pool._conn.executed) == 1

    @pytest.mark.asyncio
    async def test_이벤트_ID_고유성(self):
        """연속 호출 시 서로 다른 event_id가 생성되어야 한다."""
        conn = MockConnection()
        id1 = await publish_event(
            tenant_id="t-005", project_id="p-005",
            aggregate_type="Cube", aggregate_id="c1",
            event_type="E1", payload={}, conn=conn,
        )
        id2 = await publish_event(
            tenant_id="t-005", project_id="p-005",
            aggregate_type="Cube", aggregate_id="c2",
            event_type="E2", payload={}, conn=conn,
        )
        assert id1 != id2


# ──────────────────────────────────────────────
# 테스트: OlapRelayWorker 설정 및 생명주기
# ──────────────────────────────────────────────

class TestOlapRelayWorker:
    """OlapRelayWorker의 생성, 설정, 종료 로직을 검증한다."""

    def test_릴레이_워커_생성(self):
        """OlapRelayWorker를 기본 파라미터로 인스턴스화할 수 있어야 한다."""
        worker = OlapRelayWorker()
        assert worker._running is True
        assert worker._poll == 5
        assert worker._batch == 100

    def test_릴레이_워커_종료(self):
        """shutdown() 호출 시 _running이 False가 되어야 한다."""
        worker = OlapRelayWorker()
        assert worker._running is True
        worker.shutdown()
        assert worker._running is False

    def test_릴레이_워커_설정(self):
        """poll_interval과 max_batch를 커스터마이즈할 수 있어야 한다."""
        worker = OlapRelayWorker(poll_interval=10, max_batch=50)
        assert worker._poll == 10
        assert worker._batch == 50

    @pytest.mark.asyncio
    async def test_릴레이_워커_Redis_없으면_건너뜀(self):
        """Redis가 없으면 _publish_once가 0/0을 반환해야 한다."""
        worker = OlapRelayWorker()

        # _get_redis가 None을 반환하도록 모킹
        with patch("app.events.outbox._get_redis", new_callable=AsyncMock, return_value=None):
            result = await worker._publish_once()

        assert result == {"published": 0, "failed": 0}
