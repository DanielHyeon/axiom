"""G08: MongoDB 어댑터 — experimental 등급.

MongoDB 컬렉션을 테이블로 매핑, 샘플링 기반 스키마 추론.
motor 비동기 드라이버 사용.

connection 파라미터:
- uri: MongoDB 연결 URI (예: mongodb://localhost:27017)
- database: 데이터베이스명
- auth_source: 인증 DB (기본: admin)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.mongodb")

try:
    import motor.motor_asyncio as motor  # type: ignore
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False

# 샘플 문서 수 — 스키마 추론용
_SAMPLE_SIZE = 100


def _infer_bson_type(value: Any) -> str:
    """BSON/Python 값에서 Axiom 표준 타입 추론"""
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "DECIMAL"
    if isinstance(value, str):
        return "TEXT"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "JSON"
    if isinstance(value, bytes):
        return "BINARY"
    # ObjectId, datetime 등
    type_name = type(value).__name__
    if type_name == "ObjectId":
        return "UUID"
    if type_name == "datetime":
        return "TIMESTAMP"
    return "TEXT"


class MongoDBAdapter(DatabaseAdapter):
    """MongoDB 어댑터 — 컬렉션 기반 스키마 추론.

    컬렉션 = 테이블, 필드 = 컬럼. 문서 샘플링으로 스키마 추론.
    """

    engine = "mongodb"

    def _validate(self) -> None:
        if not HAS_MOTOR:
            raise ImportError("pip install motor")

    def _get_client(self) -> Any:
        """motor AsyncIOMotorClient 생성"""
        uri = self.connection.get("uri", "mongodb://localhost:27017")
        return motor.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)

    def _get_db(self, client: Any) -> Any:
        """데이터베이스 참조"""
        db_name = self.connection.get("database", "test")
        return client[db_name]

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            client = self._get_client()
            try:
                # 서버 정보 조회로 연결 확인
                await client.server_info()
            finally:
                client.close()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """MongoDB에서 스키마 = 데이터베이스 목록"""
        self._validate()
        database = self.connection.get("database", "")
        if database:
            return [database]
        client = self._get_client()
        try:
            dbs = await client.list_database_names()
            # 시스템 DB 제외
            return [d for d in dbs if d not in ("admin", "config", "local")]
        finally:
            client.close()

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """컬렉션 목록 + 샘플링 기반 스키마 추론"""
        self._validate()
        client = self._get_client()
        try:
            db = client[schema]
            collections = await db.list_collection_names()

            tables = []
            for coll_name in sorted(collections):
                # 시스템 컬렉션 건너뜀
                if coll_name.startswith("system."):
                    continue

                coll = db[coll_name]

                # 샘플 문서에서 스키마 추론
                columns = await self._infer_collection_schema(coll)

                entry: dict[str, Any] = {
                    "name": coll_name,
                    "columns": columns,
                    "source_specific": {"collection": coll_name, "type": "collection"},
                }

                if include_row_counts:
                    entry["row_count"] = await coll.estimated_document_count()

                tables.append(entry)

            return tables
        finally:
            client.close()

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """MongoDB는 FK를 지원하지 않음"""
        return []

    # ── 내부 메서드 ── #

    async def _infer_collection_schema(self, collection: Any) -> list[dict]:
        """컬렉션에서 샘플 문서를 가져와 필드 → 컬럼 매핑.

        여러 문서의 필드를 병합하여 완전한 스키마를 추론한다.
        """
        try:
            cursor = collection.find().limit(_SAMPLE_SIZE)
            # 모든 문서에서 필드 수집
            field_types: dict[str, str] = {}
            async for doc in cursor:
                for key, value in doc.items():
                    if key == "_id":
                        field_types.setdefault("_id", "UUID")
                        continue
                    inferred = _infer_bson_type(value)
                    existing = field_types.get(key)
                    if existing is None:
                        field_types[key] = inferred
                    elif existing != inferred:
                        # 타입 충돌 — 더 일반적인 타입으로 승격
                        field_types[key] = "TEXT"

            # _id를 첫 번째로
            columns = []
            if "_id" in field_types:
                columns.append({"name": "_id", "type": "UUID", "nullable": False})
            for name, ftype in sorted(field_types.items()):
                if name == "_id":
                    continue
                columns.append({"name": name, "type": ftype, "nullable": True})

            return columns if columns else [{"name": "_id", "type": "UUID", "nullable": False}]

        except Exception as e:
            logger.warning("MongoDB 스키마 추론 실패: %s — %s", collection.name, e)
            return [{"name": "_id", "type": "UUID", "nullable": False}]


def _register():
    AdapterFactory.register("mongodb", MongoDBAdapter)
    register_manifest(ConnectorManifest(
        engine="mongodb", display_name="MongoDB",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="MongoDB — motor 비동기 드라이버 + 샘플링 스키마 추론",
    ))

_register()
