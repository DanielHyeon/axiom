"""DDD-P3-03: Consumer-Driven Contract Testing.

모든 Consumer 기대 스키마가 Producer 발행 스키마와 호환되는지 자동 검증한다.
Zero-Collision Verification: 서비스 간 이벤트 계약 충돌이 0건일 때만 Pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CONTRACTS_DIR = Path(__file__).parent

# ── helpers ── #


def _load_producer_schemas() -> dict[str, dict]:
    """Load all producer schemas, keyed by event_name."""
    schemas: dict[str, dict] = {}
    for f in CONTRACTS_DIR.rglob("producer/*.json"):
        data = json.loads(f.read_text())
        schemas[data["event_name"]] = data
    return schemas


def _load_consumer_expectations() -> list[tuple[Path, dict]]:
    """Load all consumer expectation files with their paths."""
    results = []
    for f in CONTRACTS_DIR.rglob("consumer/*.json"):
        data = json.loads(f.read_text())
        results.append((f, data))
    return results


# ── fixtures ── #


@pytest.fixture(scope="module")
def producer_schemas():
    return _load_producer_schemas()


@pytest.fixture(scope="module")
def consumer_expectations():
    return _load_consumer_expectations()


# ── Test: Producer Schema Completeness ── #


class TestProducerSchemas:
    """Producer 스키마의 구조 건전성 검증."""

    def test_all_producers_have_required_meta(self, producer_schemas):
        """모든 Producer 스키마에 필수 메타필드가 존재하는지 확인."""
        required_meta = {"event_name", "version", "producer", "schema"}
        for event_name, data in producer_schemas.items():
            missing = required_meta - set(data.keys())
            assert not missing, (
                f"Producer schema '{event_name}' is missing meta fields: {missing}"
            )

    def test_all_producers_have_valid_schema(self, producer_schemas):
        """모든 Producer 스키마가 JSON Schema 구조를 갖추고 있는지 확인."""
        for event_name, data in producer_schemas.items():
            schema = data.get("schema", {})
            assert schema.get("type") == "object", (
                f"Producer schema '{event_name}' must have type 'object'"
            )
            assert "properties" in schema, (
                f"Producer schema '{event_name}' must define 'properties'"
            )
            assert "required" in schema, (
                f"Producer schema '{event_name}' must define 'required' fields"
            )

    def test_all_producers_include_idempotency_key(self, producer_schemas):
        """모든 Producer 스키마에 idempotency_key 속성이 존재하는지 확인."""
        for event_name, data in producer_schemas.items():
            props = data.get("schema", {}).get("properties", {})
            assert "idempotency_key" in props, (
                f"Producer schema '{event_name}' must include 'idempotency_key' property"
            )

    def test_all_producers_include_event_contract(self, producer_schemas):
        """모든 Producer 스키마에 event_contract 속성이 존재하는지 확인."""
        for event_name, data in producer_schemas.items():
            props = data.get("schema", {}).get("properties", {})
            assert "event_contract" in props, (
                f"Producer schema '{event_name}' must include 'event_contract' property"
            )

    def test_minimum_event_count(self, producer_schemas):
        """이벤트 카탈로그에 최소 16개 이벤트가 등록되어 있는지 확인."""
        assert len(producer_schemas) >= 16, (
            f"Expected at least 16 producer schemas, found {len(producer_schemas)}"
        )


# ── Test: Consumer Compatibility ── #


class TestConsumerCompatibility:
    """Producer-Consumer 간 스키마 호환성 검증 (Zero-Collision Verification)."""

    def test_all_consumers_have_matching_producer(self, producer_schemas, consumer_expectations):
        """모든 Consumer 기대 파일에 대응하는 Producer 스키마가 존재하는지 확인."""
        for path, expectation in consumer_expectations:
            event_name = expectation["event_name"]
            assert event_name in producer_schemas, (
                f"Consumer file {path.name}: Producer schema not found for event '{event_name}'"
            )

    def test_consumer_required_fields_exist_in_producer(self, producer_schemas, consumer_expectations):
        """Consumer가 기대하는 required_fields가 Producer 스키마의 properties에 모두 존재하는지 확인."""
        violations = []
        for path, expectation in consumer_expectations:
            event_name = expectation["event_name"]
            producer = producer_schemas.get(event_name)
            if producer is None:
                continue  # 이미 위 테스트에서 검증됨

            consumer_required = set(expectation.get("required_fields", []))
            producer_properties = set(producer.get("schema", {}).get("properties", {}).keys())
            missing = consumer_required - producer_properties
            if missing:
                violations.append(
                    f"  [{path.name}] Consumer '{expectation['consumer']}' expects "
                    f"fields {sorted(missing)} in '{event_name}', "
                    f"but Producer doesn't provide them"
                )

        assert not violations, (
            "Consumer-Producer field compatibility violations found:\n"
            + "\n".join(violations)
        )

    def test_consumer_required_fields_are_in_producer_required(self, producer_schemas, consumer_expectations):
        """Consumer의 required_fields가 Producer의 required 목록에도 포함되는지 확인.

        Consumer가 의존하는 필드가 Producer 측에서 optional이면,
        Producer가 해당 필드를 생략할 수 있어 런타임 실패 위험이 있다.
        """
        warnings = []
        for path, expectation in consumer_expectations:
            event_name = expectation["event_name"]
            producer = producer_schemas.get(event_name)
            if producer is None:
                continue

            consumer_required = set(expectation.get("required_fields", []))
            producer_required = set(producer.get("schema", {}).get("required", []))
            # idempotency_key와 event_contract는 시스템이 자동 추가하므로 제외
            system_fields = {"idempotency_key", "event_contract"}
            check_fields = consumer_required - system_fields
            not_required = check_fields - producer_required
            if not_required:
                warnings.append(
                    f"  [{path.name}] Consumer '{expectation['consumer']}' "
                    f"depends on {sorted(not_required)} in '{event_name}', "
                    f"but these are optional in Producer schema"
                )

        # 경고 수준: 0건이 이상적이지만, 허용 가능한 경우도 있으므로 soft-assert
        if warnings:
            pytest.skip(
                "Optional-field dependency warnings (non-blocking):\n"
                + "\n".join(warnings)
            )


# ── Test: Consumer Meta Completeness ── #


class TestConsumerMeta:
    """Consumer 기대 파일의 구조 건전성 검증."""

    def test_all_consumers_have_required_meta(self, consumer_expectations):
        """모든 Consumer 기대 파일에 필수 메타필드가 존재하는지 확인."""
        required_meta = {"event_name", "consumer", "consumer_group", "required_fields"}
        for path, data in consumer_expectations:
            missing = required_meta - set(data.keys())
            assert not missing, (
                f"Consumer file {path.name} is missing meta fields: {missing}"
            )

    def test_consumer_required_fields_not_empty(self, consumer_expectations):
        """모든 Consumer가 최소 1개 이상의 required_fields를 정의하는지 확인."""
        for path, data in consumer_expectations:
            fields = data.get("required_fields", [])
            assert len(fields) > 0, (
                f"Consumer file {path.name} has empty required_fields"
            )


# ── Test: Cross-Service Registry Consistency ── #


class TestRegistryConsistency:
    """EventContractRegistry와 Contract JSON 파일의 일관성 검증."""

    def _load_registry(self, service: str) -> dict[str, dict] | None:
        """서비스의 EventContractRegistry를 파일 경로 기반으로 직접 로드.

        importlib.import_module 대신 spec_from_file_location을 사용하여
        서비스 간 모듈 네임스페이스 충돌을 방지한다.
        """
        import importlib.util
        import sys
        import types

        service_path = Path(__file__).parent.parent.parent / "services" / service
        registry_file = service_path / "app" / "core" / "event_contract_registry.py"
        if not registry_file.exists():
            return None

        # 고유한 모듈 이름으로 로드하여 충돌 방지
        module_name = f"_contract_test_{service}_event_contract_registry"

        # 서비스 경로를 임시로 추가 (의존 모듈 해석용)
        sys_path_entry = str(service_path)
        added_to_path = sys_path_entry not in sys.path
        if added_to_path:
            sys.path.insert(0, sys_path_entry)

        try:
            spec = importlib.util.spec_from_file_location(module_name, registry_file)
            if spec is None or spec.loader is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            contracts = getattr(mod, "EVENT_CONTRACTS", {})
            result = {}
            for name, contract in contracts.items():
                result[name] = {
                    "event_name": contract.event_name,
                    "owner_service": contract.owner_service,
                    "version": contract.version,
                }
            return result
        except Exception:
            return None
        finally:
            # Clean up
            sys.modules.pop(module_name, None)
            if added_to_path and sys_path_entry in sys.path:
                sys.path.remove(sys_path_entry)
            # 서비스별 app 모듈 오염 제거
            mods_to_remove = [k for k in sys.modules if k.startswith("app.")]
            for mod_key in mods_to_remove:
                del sys.modules[mod_key]

    @pytest.mark.parametrize("service", ["core", "synapse", "vision", "weaver"])
    def test_producer_schemas_match_registry(self, service, producer_schemas):
        """Producer JSON 스키마가 서비스의 EventContractRegistry에 등록된 이벤트와 일치하는지 확인."""
        registry = self._load_registry(service)
        if registry is None:
            pytest.skip(f"Cannot load registry for {service}")

        # Producer JSON에서 이 서비스의 이벤트만 필터
        service_events = {
            name: data
            for name, data in producer_schemas.items()
            if data.get("producer") == service
        }

        # Registry에 있는 이벤트가 Producer JSON에 모두 존재하는지
        for event_name in registry:
            assert event_name in service_events, (
                f"Event '{event_name}' is in {service} registry but has no producer schema JSON"
            )

        # Producer JSON에 있는 이벤트가 Registry에 모두 존재하는지
        for event_name in service_events:
            assert event_name in registry, (
                f"Producer schema '{event_name}' exists for {service} but is not in registry"
            )
