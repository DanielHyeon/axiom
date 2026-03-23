"""G09: REST API 어댑터 — experimental 등급.

REST API 엔드포인트를 테이블처럼 취급하여 메타데이터를 인트로스펙션한다.
OpenAPI/Swagger 스키마 자동 파싱 + JSON 응답 → 플랫 컬럼 스키마 변환.

connection 파라미터:
- base_url: API 베이스 URL (예: https://api.example.com/v1)
- auth_type: none | bearer | api_key | basic (인증 유형)
- auth_token: Bearer 토큰 또는 API 키 값
- auth_header: API 키 헤더명 (기본: X-Api-Key)
- openapi_url: OpenAPI 스키마 URL (선택 — 없으면 엔드포인트 탐사)
- endpoints: 수동 지정 엔드포인트 목록 (선택, JSON 배열)
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

logger = logging.getLogger("axiom.weaver.adapters.rest_api")

try:
    import httpx  # type: ignore
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# M1: 응답 최대 크기 (10MB)
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _infer_json_type(value: Any) -> str:
    """JSON 값에서 Axiom 표준 타입 추론"""
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "DECIMAL"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "JSON"
    return "TEXT"


def _flatten_json_schema(obj: dict, prefix: str = "") -> list[dict]:
    """중첩 JSON 객체를 플랫 컬럼 목록으로 변환.

    예: {"user": {"name": "홍길동"}} → [{"name": "user.name", "type": "TEXT"}]
    최대 2단계 중첩만 풀어낸다 (과도한 플래트닝 방지).
    """
    columns = []
    for key, value in obj.items():
        col_name = f"{prefix}.{key}" if prefix else key  # m1 수정
        if isinstance(value, dict) and not prefix:
            # 1단계 중첩만 풀기
            columns.extend(_flatten_json_schema(value, col_name))
        else:
            columns.append({
                "name": col_name,
                "type": _infer_json_type(value),
                "nullable": True,
            })
    return columns


def _safe_parse_json(resp: Any) -> Any:
    """M1: 응답 크기 검증 후 JSON 파싱"""
    if len(resp.content) > _MAX_RESPONSE_BYTES:
        raise ValueError(f"응답 크기 초과: {len(resp.content)} bytes (최대 {_MAX_RESPONSE_BYTES})")
    return resp.json()


class RestApiAdapter(DatabaseAdapter):
    """REST API 어댑터 — 엔드포인트를 테이블로 매핑.

    OpenAPI 스키마가 있으면 파싱하고, 없으면 수동 엔드포인트 목록을 사용한다.
    """

    engine = "rest_api"

    def _validate(self) -> None:
        if not HAS_HTTPX:
            raise ImportError("pip install httpx")
        # C1: SSRF 방어 — base_url + openapi_url 검증
        validate_external_url(self.connection.get("base_url", ""), "base_url")
        openapi_url = self.connection.get("openapi_url", "")
        if openapi_url:
            validate_external_url(openapi_url, "openapi_url")

    def _get_client(self) -> Any:
        """httpx 비동기 클라이언트 생성 — 인증 헤더 포함"""
        headers: dict[str, str] = {"Accept": "application/json"}
        auth_type = self.connection.get("auth_type", "none")
        auth_token = self.connection.get("auth_token", "")

        if auth_type == "bearer" and auth_token:
            headers["Authorization"] = f"Bearer {validate_header_value(auth_token)}"
        elif auth_type == "api_key" and auth_token:
            # C4: 헤더명 허용 목록 + CRLF 차단
            header_name = validate_auth_header(
                self.connection.get("auth_header", "X-Api-Key")
            )
            headers[header_name] = validate_header_value(auth_token)
        elif auth_type == "basic" and auth_token:
            import base64
            validated = validate_header_value(auth_token)
            headers["Authorization"] = f"Basic {base64.b64encode(validated.encode()).decode()}"

        return httpx.AsyncClient(
            base_url=self.connection.get("base_url", ""),
            headers=headers,
            timeout=10.0,
            follow_redirects=False,  # C3: SSRF 리다이렉트 우회 방지
        )

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            async with self._get_client() as client:
                openapi_url = self.connection.get("openapi_url", "")
                url = openapi_url or "/"
                resp = await client.get(url)
                resp.raise_for_status()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """REST API는 단일 스키마 (base_url)"""
        return ["api"]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        endpoints = await self._discover_endpoints()

        tables = []
        async with self._get_client() as client:
            for ep in endpoints:
                columns = await self._infer_endpoint_schema(client, ep)
                tables.append({
                    "name": ep.lstrip("/").replace("/", "_") or "root",
                    "columns": columns,
                    "source_specific": {"endpoint": ep, "method": "GET"},
                })

        return tables

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        return []

    # ── 내부 메서드 ── #

    async def _discover_endpoints(self) -> list[str]:
        """엔드포인트 목록 발견 — OpenAPI 또는 수동 목록"""
        manual = self.connection.get("endpoints", [])
        if manual:
            if isinstance(manual, str):
                import json
                try:
                    manual = json.loads(manual)
                except (ValueError, TypeError):
                    manual = [manual]  # m3: 단일 엔드포인트로 취급
            return list(manual)

        openapi_url = self.connection.get("openapi_url", "")
        if openapi_url:
            try:
                async with self._get_client() as client:
                    resp = await client.get(openapi_url)
                    resp.raise_for_status()
                    spec = _safe_parse_json(resp)
                    return self._extract_get_paths(spec)
            except Exception as e:
                logger.warning("OpenAPI 스키마 파싱 실패: %s — %s", openapi_url, e)

        return []

    def _extract_get_paths(self, spec: dict) -> list[str]:
        """OpenAPI 스키마에서 GET 메서드가 있는 경로 추출"""
        paths = spec.get("paths", {})
        endpoints = []
        for path, methods in paths.items():
            if isinstance(methods, dict) and "get" in methods:
                if "{" not in path:
                    endpoints.append(path)
        return sorted(endpoints)

    async def _infer_endpoint_schema(self, client: Any, endpoint: str) -> list[dict]:
        """GET 요청 후 JSON 응답에서 컬럼 스키마 추론"""
        try:
            resp = await client.get(endpoint)
            resp.raise_for_status()
            data = _safe_parse_json(resp)

            if isinstance(data, list) and data:
                sample = data[0]
                if isinstance(sample, dict):
                    return _flatten_json_schema(sample)

            if isinstance(data, dict):
                for key in ("data", "results", "items", "records"):
                    items = data.get(key, [])
                    if isinstance(items, list) and items and isinstance(items[0], dict):
                        return _flatten_json_schema(items[0])
                return _flatten_json_schema(data)

        except Exception as e:
            logger.warning("REST 스키마 추론 실패: %s — %s", endpoint, e)

        return [{"name": "data", "type": "JSON", "nullable": True}]


def _register():
    AdapterFactory.register("rest_api", RestApiAdapter)
    register_manifest(ConnectorManifest(
        engine="rest_api", display_name="REST API",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="REST API — httpx + OpenAPI/JSON 스키마 추론",
    ))

_register()
