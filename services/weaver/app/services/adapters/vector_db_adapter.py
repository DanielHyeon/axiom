"""G30: 벡터 DB 어댑터 — experimental 등급.

Pinecone, Milvus, Qdrant 등 벡터 DB의 인덱스/컬렉션 메타데이터 탐색.

connection 파라미터:
- provider: pinecone | milvus | qdrant
- host: 호스트 URL (Milvus/Qdrant)
- api_key: API 키 (Pinecone)
- environment: Pinecone 환경
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.vector_db")


class VectorDBAdapter(DatabaseAdapter):
    """벡터 DB 어댑터 — 인덱스/컬렉션 기반 메타데이터 탐색.

    MVP: 연결 테스트 + 기본 스키마 구조 반환.
    실 연동은 Phase 5에서 각 벡터 DB SDK 통합.
    """

    engine = "vector_db"

    def _validate(self) -> None:
        provider = self.connection.get("provider", "")
        if provider not in ("pinecone", "milvus", "qdrant"):
            raise ValueError(f"미지원 벡터 DB: {provider} (지원: pinecone, milvus, qdrant)")

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        provider = self.connection.get("provider", "")
        try:
            # MVP: provider별 기본 연결 확인
            if provider == "milvus":
                return await self._test_milvus()
            elif provider == "qdrant":
                return await self._test_qdrant()
            elif provider == "pinecone":
                return await self._test_pinecone()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        provider = self.connection.get("provider", "vector_db")
        return [provider]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """인덱스/컬렉션 목록 → 테이블 매핑.

        모든 벡터 DB는 공통적으로 id + vector + metadata 구조.
        """
        self._validate()
        provider = self.connection.get("provider", "")

        # MVP: 벡터 DB 공통 스키마 구조 반환
        # 실 연동은 Phase 5에서 SDK별 list_collections() 호출
        return [{
            "name": f"{provider}_default_index",
            "columns": [
                {"name": "id", "type": "UUID", "nullable": False},
                {"name": "vector", "type": "ARRAY", "nullable": False},
                {"name": "metadata", "type": "JSON", "nullable": True},
                {"name": "score", "type": "DECIMAL", "nullable": True},
            ],
            "source_specific": {
                "provider": provider,
                "type": "vector_index",
                "status": "pending_sdk_integration",
            },
        }]

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        return []

    # ── provider별 연결 테스트 ── #

    async def _test_milvus(self) -> ConnectionTestResult:
        """Milvus 연결 테스트 — pymilvus 필요"""
        start = time.monotonic()
        try:
            from pymilvus import connections  # type: ignore
            host = self.connection.get("host", "localhost")
            port = int(self.connection.get("port", 19530))
            connections.connect(alias="test", host=host, port=port, timeout=5)
            connections.disconnect("test")
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except ImportError:
            return ConnectionTestResult(False, 0, "pip install pymilvus")
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def _test_qdrant(self) -> ConnectionTestResult:
        """Qdrant 연결 테스트 — qdrant-client 필요"""
        start = time.monotonic()
        try:
            from qdrant_client import QdrantClient  # type: ignore
            host = self.connection.get("host", "localhost")
            port = int(self.connection.get("port", 6333))
            client = QdrantClient(host=host, port=port, timeout=5)
            client.get_collections()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except ImportError:
            return ConnectionTestResult(False, 0, "pip install qdrant-client")
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def _test_pinecone(self) -> ConnectionTestResult:
        """Pinecone 연결 테스트 — pinecone-client 필요"""
        start = time.monotonic()
        try:
            import pinecone  # type: ignore
            api_key = self.connection.get("api_key", "")
            if not api_key:
                return ConnectionTestResult(False, 0, "api_key 필수")
            pc = pinecone.Pinecone(api_key=api_key)
            pc.list_indexes()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except ImportError:
            return ConnectionTestResult(False, 0, "pip install pinecone-client")
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))


def _register():
    AdapterFactory.register("vector_db", VectorDBAdapter)
    register_manifest(ConnectorManifest(
        engine="vector_db", display_name="Vector DB (Pinecone/Milvus/Qdrant)",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="벡터 DB — Pinecone/Milvus/Qdrant 메타데이터 탐색",
    ))

_register()
