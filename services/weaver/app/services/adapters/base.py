"""G03: 어댑터 추상 클래스 + AdapterFactory.

OpenMetadata 스타일 추상화 — 모든 데이터소스 어댑터의 공통 인터페이스.
기존 core/adapters.py의 DataSourceAdapter를 확장하여 플러그인 패턴으로 전환한다.

설계 원칙:
- 새 DB 타입 추가 시 1개 파일만 작성 (plugin 패턴)
- 모든 어댑터는 StandardMetadata를 반환 (정규화 계층 경유)
- 기존 core/adapters.py와 호환 유지 (점진적 전환)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from app.models.capability import ConnectorManifest

logger = logging.getLogger("axiom.weaver.adapters")


class ConnectionTestResult:
    """연결 테스트 결과"""
    def __init__(self, success: bool, response_time_ms: float = 0, error: str = ""):
        self.success = success
        self.response_time_ms = response_time_ms
        self.error = error


class ExtractionProgress:
    """메타데이터 추출 진행 상황 — SSE 스트리밍용"""
    def __init__(
        self,
        phase: str,       # "connecting", "schemas", "tables", "fk", "complete", "error"
        progress: float,  # 0.0 ~ 1.0
        message: str = "",
        data: dict | None = None,
    ):
        self.phase = phase
        self.progress = progress
        self.message = message
        self.data = data or {}


class DatabaseAdapter(ABC):
    """데이터소스 어댑터 추상 클래스.

    모든 어댑터는 이 클래스를 상속하고, engine + manifest를 선언해야 한다.
    AdapterFactory에 자동 등록되어 엔진명으로 인스턴스를 생성할 수 있다.
    """

    engine: str = ""  # 하위 클래스에서 반드시 선언

    def __init__(self, connection: dict[str, Any]) -> None:
        self.connection = dict(connection)

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """연결 검증"""
        ...

    @abstractmethod
    async def get_schemas(self) -> list[str]:
        """스키마 목록 조회"""
        ...

    @abstractmethod
    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """테이블 목록 + 컬럼 정보 조회.

        반환: [{name, columns: [{name, type, nullable}], row_count?}]
        """
        ...

    @abstractmethod
    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """FK 관계 목록 조회.

        반환: [{source_schema, source_table, source_column,
                target_schema, target_table, target_column, constraint_name}]
        """
        ...

    async def execute_query(self, sql: str, limit: int = 100) -> dict:
        """SQL 실행 (Direct SQL용) — 지원하지 않는 어댑터는 NotImplementedError.

        반환: {columns, column_types, rows, row_count, execution_time_ms}
        """
        raise NotImplementedError(f"{self.engine} 어댑터는 직접 SQL 실행을 지원하지 않습니다")

    async def extract_metadata_stream(
        self,
        schemas: list[str] | None = None,
        *,
        include_row_counts: bool = False,
    ) -> AsyncGenerator[ExtractionProgress, None]:
        """6단계 스트리밍 메타데이터 추출 — 기본 구현.

        하위 클래스에서 오버라이드하여 최적화할 수 있다.
        """
        # 1. connecting (5%)
        yield ExtractionProgress("connecting", 0.05, f"{self.engine} 연결 중...")

        # 2. schemas (15%)
        all_schemas = schemas or await self.get_schemas()
        yield ExtractionProgress("schemas", 0.15, f"스키마 {len(all_schemas)}개 발견",
                                 {"schemas": all_schemas})

        # 3. tables (20-80%)
        all_tables: dict[str, list[dict]] = {}
        all_fks: list[dict] = []
        total = len(all_schemas)
        for i, schema in enumerate(all_schemas):
            tables = await self.get_tables(schema, include_row_counts=include_row_counts)
            all_tables[schema] = tables
            progress = 0.20 + (0.60 * (i + 1) / max(total, 1))
            yield ExtractionProgress("tables", progress,
                                     f"{schema}: 테이블 {len(tables)}개",
                                     {"schema": schema, "table_count": len(tables)})

        # 4. foreign_keys (85%)
        for schema in all_schemas:
            fks = await self.get_foreign_keys(schema)
            all_fks.extend(fks)
        yield ExtractionProgress("fk", 0.85, f"FK 관계 {len(all_fks)}개 발견")

        # 5. complete (100%)
        yield ExtractionProgress("complete", 1.0, "추출 완료", {
            "schemas": all_schemas,
            "tables": all_tables,
            "foreign_keys": all_fks,
        })


class AdapterFactory:
    """엔진명으로 어댑터 인스턴스 생성 — 플러그인 레지스트리.

    어댑터 등록: AdapterFactory.register("mssql", MSSQLAdapter)
    어댑터 생성: AdapterFactory.create("postgresql", connection_dict)
    """

    _registry: dict[str, type[DatabaseAdapter]] = {}

    @classmethod
    def register(cls, engine: str, adapter_class: type[DatabaseAdapter]) -> None:
        """어댑터 클래스 등록"""
        cls._registry[engine.lower()] = adapter_class
        logger.info("어댑터 등록: %s → %s", engine, adapter_class.__name__)

    @classmethod
    def create(cls, engine: str, connection: dict[str, Any]) -> DatabaseAdapter:
        """엔진명으로 어댑터 인스턴스 생성"""
        key = engine.lower().strip()
        # postgres 별칭 처리
        if key == "postgres":
            key = "postgresql"
        adapter_class = cls._registry.get(key)
        if not adapter_class:
            raise ValueError(
                f"지원하지 않는 엔진: {engine!r} "
                f"(등록된 엔진: {', '.join(cls.supported_engines())})"
            )
        return adapter_class(connection)

    @classmethod
    def supported_engines(cls) -> list[str]:
        """등록된 모든 엔진 목록"""
        return sorted(cls._registry.keys())

    @classmethod
    def is_supported(cls, engine: str) -> bool:
        """엔진 지원 여부"""
        key = engine.lower().strip()
        if key == "postgres":
            key = "postgresql"
        return key in cls._registry

    @classmethod
    def _reset_for_testing(cls) -> None:
        """테스트용 레지스트리 초기화 — 프로덕션에서 호출 금지"""
        cls._registry.clear()
