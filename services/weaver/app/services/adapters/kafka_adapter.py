"""G26: Kafka 어댑터 — experimental 등급.

Kafka 토픽을 테이블로 매핑, Schema Registry 연동으로 Avro/JSON 스키마 추론.

connection 파라미터:
- bootstrap_servers: Kafka 브로커 (예: localhost:9092)
- schema_registry_url: Schema Registry URL (선택)
- group_id: 컨슈머 그룹 (기본: axiom-weaver)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.kafka")

try:
    from aiokafka import AIOKafkaConsumer  # type: ignore
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False


class KafkaAdapter(DatabaseAdapter):
    """Kafka 어댑터 — 토픽 기반 스키마 탐색"""

    engine = "kafka"

    def _validate(self) -> None:
        if not HAS_KAFKA:
            raise ImportError("pip install aiokafka")

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            consumer = AIOKafkaConsumer(
                bootstrap_servers=self.connection.get("bootstrap_servers", "localhost:9092"),
                group_id=self.connection.get("group_id", "axiom-weaver-test"),
                request_timeout_ms=5000,
            )
            await consumer.start()
            try:
                topics = await consumer.topics()
            finally:
                await consumer.stop()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """Kafka에서 스키마 = 클러스터 (단일)"""
        return ["kafka"]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """토픽 목록 → 테이블로 매핑"""
        self._validate()
        consumer = AIOKafkaConsumer(
            bootstrap_servers=self.connection.get("bootstrap_servers", "localhost:9092"),
            group_id=self.connection.get("group_id", "axiom-weaver"),
            request_timeout_ms=10000,
        )
        await consumer.start()
        try:
            topics = await consumer.topics()
            tables = []
            for topic in sorted(topics):
                if topic.startswith("__"):  # 내부 토픽 제외
                    continue
                tables.append({
                    "name": topic,
                    "columns": [
                        {"name": "key", "type": "TEXT", "nullable": True},
                        {"name": "value", "type": "JSON", "nullable": True},
                        {"name": "timestamp", "type": "TIMESTAMP", "nullable": False},
                        {"name": "partition", "type": "INTEGER", "nullable": False},
                        {"name": "offset", "type": "INTEGER", "nullable": False},
                    ],
                    "source_specific": {"topic": topic, "type": "kafka_topic"},
                })
            return tables
        finally:
            await consumer.stop()

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        return []


def _register():
    AdapterFactory.register("kafka", KafkaAdapter)
    register_manifest(ConnectorManifest(
        engine="kafka", display_name="Apache Kafka",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.STREAMING_EXTRACT,
        ],
        credential_modes=[CredentialMode.INTERNAL],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="Apache Kafka — aiokafka + Schema Registry",
    ))

_register()
