"""CDC 로더 단위 테스트.

Debezium 이벤트 파싱, Neo4j 쿼리 생성, CDCLoader 클래스를 테스트한다.
Kafka/Neo4j 없이 순수 로직만 검증.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from app.workers.cdc_loader import (
    parse_debezium_event,
    extract_table_name,
    build_neo4j_label,
    build_neo4j_query,
    CDCLoader,
)


# ── Debezium 이벤트 파싱 테스트 ────────────────────────────────────


class TestParseDebeziumEvent:
    """Debezium CDC 이벤트 파서 테스트"""

    def test_parse_json_bytes(self):
        """바이트 문자열 이벤트를 파싱한다"""
        raw = json.dumps({"op": "c", "after": {"id": 1}}).encode("utf-8")
        result = parse_debezium_event(raw)
        assert result is not None
        assert result["op"] == "c"
        assert result["after"]["id"] == 1

    def test_parse_json_string(self):
        """일반 문자열 이벤트를 파싱한다"""
        raw = json.dumps({"op": "u", "before": {"id": 1}, "after": {"id": 1, "name": "updated"}})
        result = parse_debezium_event(raw)
        assert result["op"] == "u"

    def test_parse_with_payload_envelope(self):
        """Debezium envelope 형식을 처리한다"""
        raw = json.dumps({"payload": {"op": "d", "before": {"id": 99}}})
        result = parse_debezium_event(raw)
        assert result["op"] == "d"
        assert result["before"]["id"] == 99

    def test_parse_none_returns_none(self):
        """None 입력 시 None 반환"""
        assert parse_debezium_event(None) is None

    def test_parse_invalid_json_returns_none(self):
        """잘못된 JSON은 None 반환"""
        assert parse_debezium_event(b"not-json") is None

    def test_parse_invalid_utf8_returns_none(self):
        """잘못된 UTF-8 바이트는 None 반환"""
        assert parse_debezium_event(b"\x80\x81\x82") is None


# ── 테이블명 / 레이블 변환 테스트 ──────────────────────────────────


class TestExtractTableName:
    """소스 테이블명 추출 테스트"""

    def test_with_source_info(self):
        """source 필드에서 스키마.테이블을 추출한다"""
        event = {"source": {"schema": "public", "table": "orders"}}
        assert extract_table_name(event) == "public.orders"

    def test_without_source(self):
        """source 없으면 기본값 반환"""
        assert extract_table_name({}) == "public.unknown"

    def test_custom_schema(self):
        """커스텀 스키마 처리"""
        event = {"source": {"schema": "sales", "table": "invoices"}}
        assert extract_table_name(event) == "sales.invoices"


class TestBuildNeo4jLabel:
    """Neo4j 노드 레이블 생성 테스트"""

    def test_simple_table(self):
        """단순 테이블명 → PascalCase"""
        assert build_neo4j_label("orders") == "Orders"

    def test_snake_case(self):
        """스네이크 케이스 → PascalCase"""
        assert build_neo4j_label("order_items") == "OrderItems"

    def test_with_schema_prefix(self):
        """스키마 접두사 제거"""
        assert build_neo4j_label("public.order_items") == "OrderItems"

    def test_empty_string(self):
        """빈 문자열 → Unknown"""
        assert build_neo4j_label("") == "Unknown"


# ── Neo4j 쿼리 생성 테스트 ─────────────────────────────────────────


class TestBuildNeo4jQuery:
    """Neo4j Cypher 쿼리 빌더 테스트"""

    def test_create_event(self):
        """INSERT(c) 이벤트 → MERGE + SET 쿼리"""
        event = {
            "op": "c",
            "after": {"id": 1, "name": "Widget", "price": 9.99},
            "source": {"schema": "public", "table": "products"},
        }
        result = build_neo4j_query(event)
        assert result is not None
        cypher, params = result
        assert "MERGE" in cypher
        assert "Instance" in cypher
        assert "Products" in cypher
        assert params["pk_value"] == 1
        assert params["props"]["name"] == "Widget"

    def test_update_event(self):
        """UPDATE(u) 이벤트 → MERGE + SET 쿼리"""
        event = {
            "op": "u",
            "before": {"id": 1, "name": "Old"},
            "after": {"id": 1, "name": "New"},
            "source": {"schema": "public", "table": "products"},
        }
        result = build_neo4j_query(event)
        assert result is not None
        cypher, params = result
        assert "MERGE" in cypher
        assert params["props"]["name"] == "New"

    def test_delete_event(self):
        """DELETE(d) 이벤트 → DETACH DELETE 쿼리"""
        event = {
            "op": "d",
            "before": {"id": 42, "name": "Deleted"},
            "source": {"schema": "public", "table": "products"},
        }
        result = build_neo4j_query(event)
        assert result is not None
        cypher, params = result
        assert "DETACH DELETE" in cypher
        assert params["pk_value"] == 42

    def test_read_event(self):
        """스냅샷 읽기(r) 이벤트 → MERGE 쿼리"""
        event = {
            "op": "r",
            "after": {"id": 1, "name": "Snapshot"},
            "source": {"schema": "public", "table": "items"},
        }
        result = build_neo4j_query(event)
        assert result is not None
        cypher, _ = result
        assert "MERGE" in cypher

    def test_unknown_op_returns_none(self):
        """알 수 없는 op 코드는 None 반환"""
        event = {"op": "x", "after": {"id": 1}}
        assert build_neo4j_query(event) is None

    def test_create_without_after_returns_none(self):
        """after 없는 INSERT는 None 반환"""
        event = {"op": "c", "after": None, "source": {"table": "t"}}
        assert build_neo4j_query(event) is None

    def test_delete_without_before_returns_none(self):
        """before 없는 DELETE는 None 반환"""
        event = {"op": "d", "before": None, "source": {"table": "t"}}
        assert build_neo4j_query(event) is None

    def test_null_values_filtered(self):
        """None 값은 props에서 제외된다"""
        event = {
            "op": "c",
            "after": {"id": 1, "name": None, "active": True},
            "source": {"schema": "public", "table": "users"},
        }
        result = build_neo4j_query(event)
        assert result is not None
        _, params = result
        assert "name" not in params["props"]
        assert params["props"]["active"] is True


# ── CDCLoader 클래스 테스트 ────────────────────────────────────────


class TestCDCLoader:
    """CDCLoader 클래스 테스트"""

    def test_init_defaults(self):
        """기본 설정값으로 초기화"""
        loader = CDCLoader()
        assert loader._kafka_bootstrap == "localhost:9092"
        assert loader._kafka_group_id == "axiom-neo4j-loader"
        assert loader._processed == 0

    def test_init_custom(self):
        """커스텀 설정값 초기화"""
        loader = CDCLoader(
            kafka_bootstrap="broker:9093",
            kafka_group_id="custom-group",
            neo4j_uri="bolt://neo4j:7687",
        )
        assert loader._kafka_bootstrap == "broker:9093"
        assert loader._kafka_group_id == "custom-group"
        assert loader._neo4j_uri == "bolt://neo4j:7687"

    def test_stats_initial(self):
        """초기 통계는 모두 0"""
        loader = CDCLoader()
        assert loader.stats == {"processed": 0, "errors": 0, "skipped": 0}

    def test_process_event_valid(self):
        """유효한 이벤트 처리 (Neo4j 목 사용)"""
        loader = CDCLoader()
        # Neo4j 드라이버 목
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        loader._driver = mock_driver

        raw = json.dumps({
            "op": "c",
            "after": {"id": 1, "name": "test"},
            "source": {"schema": "public", "table": "items"},
        })

        result = loader.process_event(raw)
        assert result is True
        assert loader._processed == 1

    def test_process_event_invalid(self):
        """잘못된 이벤트는 스킵 처리"""
        loader = CDCLoader()
        result = loader.process_event(b"not-json")
        assert result is False
        assert loader._skipped == 1

    def test_process_event_neo4j_error(self):
        """Neo4j 오류 시 에러 카운트 증가"""
        loader = CDCLoader()
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("connection lost")
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        loader._driver = mock_driver

        raw = json.dumps({
            "op": "c",
            "after": {"id": 1},
            "source": {"schema": "public", "table": "t"},
        })

        result = loader.process_event(raw)
        assert result is False
        assert loader._errors == 1

    def test_cleanup(self):
        """리소스 정리"""
        loader = CDCLoader()
        mock_consumer = MagicMock()
        mock_driver = MagicMock()
        loader._consumer = mock_consumer
        loader._driver = mock_driver

        loader._cleanup()

        mock_consumer.close.assert_called_once()
        mock_driver.close.assert_called_once()
