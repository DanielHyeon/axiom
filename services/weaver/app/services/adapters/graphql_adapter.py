"""G09: GraphQL 어댑터 — experimental 등급.

GraphQL Introspection 쿼리로 타입 스키마를 추출하여
Type → 테이블, Field → 컬럼으로 매핑한다.

connection 파라미터:
- endpoint: GraphQL 엔드포인트 URL (예: https://api.example.com/graphql)
- auth_type: none | bearer | api_key (인증 유형)
- auth_token: Bearer 토큰 또는 API 키
- auth_header: API 키 헤더명 (기본: Authorization)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter
from app.services.adapters._ssrf_guard import (
    validate_external_url, validate_auth_header, validate_header_value,
)

logger = logging.getLogger("axiom.weaver.adapters.graphql")

# M1: 응답 최대 크기
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

try:
    import httpx  # type: ignore
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# GraphQL Introspection 쿼리 — 전체 타입 스키마 조회
_INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    types {
      name
      kind
      description
      fields {
        name
        description
        type {
          name
          kind
          ofType {
            name
            kind
            ofType {
              name
              kind
            }
          }
        }
      }
    }
  }
}
"""

# 내장 타입 (스키마에서 제외)
_BUILTIN_TYPES = {
    "String", "Int", "Float", "Boolean", "ID",
    "__Schema", "__Type", "__Field", "__InputValue",
    "__EnumValue", "__Directive", "__DirectiveLocation",
}

# GraphQL 타입 → Axiom 표준 타입 매핑
_GRAPHQL_TYPE_MAP: dict[str, str] = {
    "String": "TEXT",
    "Int": "INTEGER",
    "Float": "DECIMAL",
    "Boolean": "BOOLEAN",
    "ID": "UUID",
}


class GraphQLAdapter(DatabaseAdapter):
    """GraphQL 어댑터 — Introspection 기반 스키마 추출.

    OBJECT 타입 = 테이블, 필드 = 컬럼으로 매핑한다.
    """

    engine = "graphql"

    # M4: Introspection 결과 캐시 (get_tables + get_foreign_keys 중복 요청 방지)
    _introspection_cache: dict | None = None

    def _validate(self) -> None:
        if not HAS_HTTPX:
            raise ImportError("pip install httpx")
        # C2: SSRF 방어 — endpoint URL 검증
        validate_external_url(self.connection.get("endpoint", ""), "endpoint")

    def _get_headers(self) -> dict[str, str]:
        """인증 헤더 생성 — C4: 헤더 인젝션 방지"""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        auth_type = self.connection.get("auth_type", "none")
        auth_token = self.connection.get("auth_token", "")

        if auth_type == "bearer" and auth_token:
            headers["Authorization"] = f"Bearer {validate_header_value(auth_token)}"
        elif auth_type == "api_key" and auth_token:
            header_name = validate_auth_header(
                self.connection.get("auth_header", "Authorization")
            )
            headers[header_name] = validate_header_value(auth_token)

        return headers

    async def _get_introspection(self) -> dict:
        """M4: Introspection 결과 캐시 — 중복 HTTP 요청 방지"""
        if self._introspection_cache is not None:
            return self._introspection_cache
        endpoint = self.connection.get("endpoint", "")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                endpoint,
                headers=self._get_headers(),
                json={"query": _INTROSPECTION_QUERY},
            )
            resp.raise_for_status()
            # M1: 응답 크기 검증
            if len(resp.content) > _MAX_RESPONSE_BYTES:
                raise ValueError(f"Introspection 응답 크기 초과: {len(resp.content)} bytes")
            self._introspection_cache = resp.json()
        return self._introspection_cache

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            endpoint = self.connection.get("endpoint", "")
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 간단한 Introspection 쿼리로 연결 확인
                resp = await client.post(
                    endpoint,
                    headers=self._get_headers(),
                    json={"query": "{ __schema { queryType { name } } }"},
                )
                resp.raise_for_status()
                data = resp.json()
                if "errors" in data and not data.get("data"):
                    return ConnectionTestResult(
                        False,
                        (time.monotonic() - start) * 1000,
                        str(data["errors"]),
                    )
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """GraphQL은 단일 스키마"""
        return ["graphql"]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """Introspection → OBJECT 타입 = 테이블, 필드 = 컬럼"""
        self._validate()
        data = await self._get_introspection()

        schema_data = data.get("data", {}).get("__schema", {})
        types = schema_data.get("types", [])

        tables = []
        for gql_type in types:
            name = gql_type.get("name", "")
            kind = gql_type.get("kind", "")

            # OBJECT 타입만 + 내장/언더스코어 접두사 제외
            if kind != "OBJECT" or name.startswith("__") or name in _BUILTIN_TYPES:
                continue

            fields = gql_type.get("fields", []) or []
            columns = []
            for field in fields:
                col_name = field.get("name", "")
                col_type = self._resolve_field_type(field.get("type", {}))
                nullable = not self._is_non_null(field.get("type", {}))

                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "nullable": nullable,
                })

            tables.append({
                "name": name,
                "columns": columns,
                "source_specific": {
                    "graphql_kind": kind,
                    "description": gql_type.get("description", ""),
                },
            })

        return sorted(tables, key=lambda t: t["name"])

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """GraphQL 타입 간 참조를 FK로 변환.

        OBJECT 타입 필드가 다른 OBJECT를 참조하면 FK 관계로 매핑한다.
        """
        self._validate()
        data = await self._get_introspection()

        schema_data = data.get("data", {}).get("__schema", {})
        types = schema_data.get("types", [])

        # OBJECT 타입 이름 집합
        object_types = {
            t["name"] for t in types
            if t.get("kind") == "OBJECT"
            and not t["name"].startswith("__")
            and t["name"] not in _BUILTIN_TYPES
        }

        fks = []
        for gql_type in types:
            source_name = gql_type.get("name", "")
            if source_name not in object_types:
                continue

            for field in (gql_type.get("fields") or []):
                target_type = self._resolve_base_type_name(field.get("type", {}))
                if target_type in object_types and target_type != source_name:
                    fks.append({
                        "source_schema": "graphql",
                        "source_table": source_name,
                        "source_column": field.get("name", ""),
                        "target_schema": "graphql",
                        "target_table": target_type,
                        "target_column": "id",  # GraphQL 관례: id 필드
                        "constraint_name": f"gql_{source_name}_{field.get('name', '')}",
                    })

        return fks

    # ── 내부 메서드 ── #

    def _resolve_field_type(self, type_info: dict) -> str:
        """GraphQL 타입 정보 → Axiom 표준 타입"""
        name = type_info.get("name")
        kind = type_info.get("kind", "")

        if name and name in _GRAPHQL_TYPE_MAP:
            return _GRAPHQL_TYPE_MAP[name]

        if kind == "NON_NULL":
            return self._resolve_field_type(type_info.get("ofType", {}))

        if kind == "LIST":
            return "ARRAY"

        if kind == "OBJECT":
            return "JSON"

        if kind == "ENUM":
            return "TEXT"

        # 중첩 ofType 탐색
        of_type = type_info.get("ofType")
        if of_type:
            return self._resolve_field_type(of_type)

        return "TEXT"

    def _is_non_null(self, type_info: dict) -> bool:
        """NON_NULL 타입인지 확인"""
        return type_info.get("kind") == "NON_NULL"

    def _resolve_base_type_name(self, type_info: dict) -> str:
        """중첩 타입에서 기본 타입 이름 추출 (NON_NULL/LIST 벗기기)"""
        name = type_info.get("name")
        if name:
            return name
        of_type = type_info.get("ofType")
        if of_type:
            return self._resolve_base_type_name(of_type)
        return ""


def _register():
    AdapterFactory.register("graphql", GraphQLAdapter)
    register_manifest(ConnectorManifest(
        engine="graphql", display_name="GraphQL API",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="GraphQL — Introspection 기반 타입 스키마 추출",
    ))

_register()
