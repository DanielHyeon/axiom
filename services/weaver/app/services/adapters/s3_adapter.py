"""G10: S3 어댑터 — experimental 등급.

AWS S3 / MinIO 파일 스토리지의 메타데이터 인트로스펙션.
파일 목록 탐색 → 샘플링 → PyArrow로 스키마 추론.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.s3")

import ipaddress
import socket
from urllib.parse import urlparse

try:
    import boto3  # type: ignore
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# SSRF 방지: 내부 네트워크 차단 (리뷰 #2 수정)
_BLOCKED_NETS = [
    ipaddress.ip_network("169.254.0.0/16"),  # AWS 메타데이터
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]

def _validate_endpoint_url(url: str) -> str:
    """S3 endpoint URL SSRF 검증 — 내부 네트워크 차단"""
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"허용되지 않는 프로토콜: {parsed.scheme}")
    hostname = parsed.hostname or ""
    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or 443)
        for _, _, _, _, addr in resolved:
            ip = ipaddress.ip_address(addr[0])
            for net in _BLOCKED_NETS:
                if ip in net:
                    raise ValueError(f"내부 네트워크 접근 차단: {hostname} → {ip}")
    except socket.gaierror:
        pass  # DNS 해석 실패는 연결 시점에서 처리
    return url


class S3Adapter(DatabaseAdapter):
    """S3/MinIO 어댑터 — 파일 기반 스키마 추론.

    connection 파라미터:
    - bucket: S3 버킷명
    - prefix: 키 접두사 (폴더 경로)
    - region: AWS 리전 (기본: us-east-1)
    - endpoint_url: MinIO 등 커스텀 엔드포인트 (선택)
    - access_key, secret_key: 인증 (선택 — IAM 역할 가능)
    """

    engine = "s3"

    def _validate(self) -> None:
        if not HAS_BOTO3:
            raise ImportError("pip install boto3")

    def _get_client(self) -> Any:
        kwargs: dict[str, Any] = {
            "region_name": self.connection.get("region", "us-east-1"),
        }
        endpoint = self.connection.get("endpoint_url", "")
        if endpoint:
            kwargs["endpoint_url"] = _validate_endpoint_url(endpoint)
        ak = self.connection.get("access_key", "")
        sk = self.connection.get("secret_key", "")
        if ak and sk:
            kwargs["aws_access_key_id"] = ak
            kwargs["aws_secret_access_key"] = sk
        return boto3.client("s3", **kwargs)

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            def _test():
                client = self._get_client()
                bucket = self.connection.get("bucket", "")
                client.head_bucket(Bucket=bucket)
            await asyncio.to_thread(_test)
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """S3에서 스키마 = 버킷 내 최상위 prefix"""
        self._validate()
        bucket = self.connection.get("bucket", "")
        prefix = self.connection.get("prefix", "")
        def _fetch():
            client = self._get_client()
            resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter="/", MaxKeys=100)
            prefixes = resp.get("CommonPrefixes", [])
            return [p["Prefix"].rstrip("/") for p in prefixes] or [prefix.rstrip("/") or bucket]
        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """S3 파일 → 테이블로 매핑.

        CSV/Parquet/JSON 파일을 발견하면 PyArrow로 스키마 추론.
        각 파일 = 1 테이블로 취급 (같은 형식의 파일은 그룹핑 가능).
        """
        self._validate()
        bucket = self.connection.get("bucket", "")
        def _fetch():
            client = self._get_client()
            prefix = schema + "/" if schema else ""
            resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=200)
            files = resp.get("Contents", [])
            tables = []
            for f in files:
                key = f["Key"]
                name = key.rsplit("/", 1)[-1]
                if not name:
                    continue
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                # 지원 형식: CSV, Parquet, JSON
                if ext not in ("csv", "parquet", "json", "jsonl"):
                    continue
                columns = _infer_schema_from_s3(client, bucket, key, ext)
                entry: dict[str, Any] = {
                    "name": name,
                    "columns": columns,
                    "source_specific": {"s3_key": key, "format": ext, "size": f.get("Size", 0)},
                }
                tables.append(entry)
            return tables
        return await asyncio.to_thread(_fetch)

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """파일 스토리지는 FK를 지원하지 않음"""
        return []


def _infer_schema_from_s3(client: Any, bucket: str, key: str, ext: str) -> list[dict]:
    """S3 파일에서 스키마 추론 — 첫 1MB만 다운로드하여 PyArrow/csv로 파싱"""
    try:
        if ext == "parquet":
            try:
                import pyarrow.parquet as pq  # type: ignore
                import io
                obj = client.get_object(Bucket=bucket, Key=key, Range="bytes=0-1048576")
                # Parquet 메타데이터는 파일 끝에 있으므로 전체 다운로드 필요할 수 있음
                # 작은 파일만 추론, 큰 파일은 메타데이터만
                body = obj["Body"].read()
                pf = pq.ParquetFile(io.BytesIO(body))
                schema = pf.schema_arrow
                return [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema]
            except Exception:
                return [{"name": "data", "type": "unknown", "nullable": True}]

        elif ext == "csv":
            import csv
            import io
            obj = client.get_object(Bucket=bucket, Key=key, Range="bytes=0-8192")
            body = obj["Body"].read().decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(body))
            header = next(reader, None)
            if header:
                return [{"name": col.strip(), "type": "TEXT", "nullable": True} for col in header]
            return []

        elif ext in ("json", "jsonl"):
            import json
            import io
            obj = client.get_object(Bucket=bucket, Key=key, Range="bytes=0-8192")
            body = obj["Body"].read().decode("utf-8", errors="ignore")
            first_line = body.strip().split("\n")[0]
            data = json.loads(first_line)
            if isinstance(data, dict):
                return [{"name": k, "type": _infer_json_type(v), "nullable": True} for k, v in data.items()]
            return []
    except Exception as e:
        logger.warning("S3 스키마 추론 실패: %s/%s — %s", bucket, key, e)
    return []


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


def _register():
    AdapterFactory.register("s3", S3Adapter)
    register_manifest(ConnectorManifest(
        engine="s3", display_name="AWS S3 / MinIO",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="AWS S3 / MinIO — boto3 + PyArrow 스키마 추론",
    ))

_register()
