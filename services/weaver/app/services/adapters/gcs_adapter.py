"""G10: GCS 어댑터 — experimental 등급.

Google Cloud Storage 파일 기반 메타데이터 인트로스펙션.
S3Adapter와 동일한 스키마 추론 로직, GCS API만 다름.
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

logger = logging.getLogger("axiom.weaver.adapters.gcs")

try:
    from google.cloud import storage as gcs_storage  # type: ignore
    HAS_GCS = True
except ImportError:
    HAS_GCS = False


class GCSAdapter(DatabaseAdapter):
    """Google Cloud Storage 어댑터 — 파일 기반 스키마 추론.

    connection: bucket, prefix, project_id, credentials_json (선택)
    """

    engine = "gcs"

    def _validate(self) -> None:
        if not HAS_GCS:
            raise ImportError("pip install google-cloud-storage")

    def _get_client(self) -> Any:
        project = self.connection.get("project_id", "")
        creds_json = self.connection.get("credentials_json", "")
        if creds_json:
            import json
            from google.oauth2 import service_account  # type: ignore
            info = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
            credentials = service_account.Credentials.from_service_account_info(info)
            return gcs_storage.Client(project=project, credentials=credentials)
        return gcs_storage.Client(project=project)

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            def _test():
                client = self._get_client()
                bucket_name = self.connection.get("bucket", "")
                client.get_bucket(bucket_name)
            await asyncio.to_thread(_test)
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        self._validate()
        bucket_name = self.connection.get("bucket", "")
        prefix = self.connection.get("prefix", "")
        def _fetch():
            client = self._get_client()
            bucket = client.get_bucket(bucket_name)
            # 최상위 prefix를 스키마로 취급
            iterator = bucket.list_blobs(prefix=prefix, delimiter="/", max_results=100)
            # iterator를 소비하여 prefixes 접근
            list(iterator)  # pages 소비
            prefixes = list(iterator.prefixes)
            return [p.rstrip("/") for p in prefixes] or [prefix.rstrip("/") or bucket_name]
        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        bucket_name = self.connection.get("bucket", "")
        def _fetch():
            client = self._get_client()
            bucket = client.get_bucket(bucket_name)
            prefix = schema + "/" if schema else ""
            blobs = list(bucket.list_blobs(prefix=prefix, max_results=200))
            tables = []
            for blob in blobs:
                name = blob.name.rsplit("/", 1)[-1]
                if not name:
                    continue
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext not in ("csv", "parquet", "json", "jsonl"):
                    continue
                # GCS에서 첫 8KB 다운로드하여 스키마 추론
                columns = _infer_schema_from_gcs(blob, ext)
                tables.append({
                    "name": name,
                    "columns": columns,
                    "source_specific": {"gcs_path": f"gs://{bucket_name}/{blob.name}", "format": ext},
                })
            return tables
        return await asyncio.to_thread(_fetch)

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        return []


def _infer_schema_from_gcs(blob: Any, ext: str) -> list[dict]:
    """GCS blob에서 스키마 추론 — CSV 헤더 또는 Parquet 메타데이터"""
    try:
        if ext == "csv":
            import csv
            import io
            data = blob.download_as_text(start=0, end=8192)
            reader = csv.reader(io.StringIO(data))
            header = next(reader, None)
            if header:
                return [{"name": col.strip(), "type": "TEXT", "nullable": True} for col in header]
        elif ext in ("json", "jsonl"):
            import json
            data = blob.download_as_text(start=0, end=8192)
            first_line = data.strip().split("\n")[0]
            obj = json.loads(first_line)
            if isinstance(obj, dict):
                return [{"name": k, "type": "TEXT", "nullable": True} for k, v in obj.items()]
        # Parquet은 전체 다운로드 필요 — 스킵
    except Exception as e:
        logger.warning("GCS 스키마 추론 실패: %s — %s", blob.name, e)
    return [{"name": "data", "type": "TEXT", "nullable": True}]


def _register():
    AdapterFactory.register("gcs", GCSAdapter)
    register_manifest(ConnectorManifest(
        engine="gcs", display_name="Google Cloud Storage",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
        ],
        credential_modes=[CredentialMode.SERVICE_ACCOUNT, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="Google Cloud Storage — google-cloud-storage + CSV/JSON 스키마 추론",
    ))

_register()
