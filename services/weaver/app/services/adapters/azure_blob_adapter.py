"""G10: Azure Blob Storage 어댑터 — experimental 등급.

Azure Blob Storage 파일 기반 메타데이터 인트로스펙션.
S3/GCS와 동일한 스키마 추론 패턴, Azure SDK 사용.
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

logger = logging.getLogger("axiom.weaver.adapters.azure_blob")

try:
    from azure.storage.blob import BlobServiceClient  # type: ignore
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False


class AzureBlobAdapter(DatabaseAdapter):
    """Azure Blob Storage 어댑터 — 파일 기반 스키마 추론.

    connection: connection_string 또는 (account_url + credential), container, prefix
    """

    engine = "azure_blob"

    def _validate(self) -> None:
        if not HAS_AZURE:
            raise ImportError("pip install azure-storage-blob")

    def _get_client(self) -> Any:
        conn_str = self.connection.get("connection_string", "")
        if conn_str:
            return BlobServiceClient.from_connection_string(conn_str)
        account_url = self.connection.get("account_url", "")
        credential = self.connection.get("credential", "")
        return BlobServiceClient(account_url=account_url, credential=credential)

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            def _test():
                client = self._get_client()
                container = self.connection.get("container", "")
                cc = client.get_container_client(container)
                cc.get_container_properties()
            await asyncio.to_thread(_test)
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """Azure에서 스키마 = 컨테이너 내 최상위 virtual directory"""
        self._validate()
        container = self.connection.get("container", "")
        prefix = self.connection.get("prefix", "")
        def _fetch():
            client = self._get_client()
            cc = client.get_container_client(container)
            # delimiter로 virtual directory 탐색
            blobs = cc.walk_blobs(name_starts_with=prefix, delimiter="/")
            dirs = []
            for item in blobs:
                if hasattr(item, "prefix"):
                    dirs.append(item.prefix.rstrip("/"))
            return dirs or [prefix.rstrip("/") or container]
        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        container = self.connection.get("container", "")
        def _fetch():
            client = self._get_client()
            cc = client.get_container_client(container)
            prefix = schema + "/" if schema else ""
            blobs = list(cc.list_blobs(name_starts_with=prefix))
            tables = []
            for blob in blobs[:200]:
                name = blob.name.rsplit("/", 1)[-1]
                if not name:
                    continue
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext not in ("csv", "parquet", "json", "jsonl"):
                    continue
                # Azure에서 첫 8KB 다운로드
                columns = _infer_schema_from_azure(cc, blob.name, ext)
                tables.append({
                    "name": name,
                    "columns": columns,
                    "source_specific": {"azure_path": f"{container}/{blob.name}", "format": ext},
                })
            return tables
        return await asyncio.to_thread(_fetch)

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        return []


def _infer_schema_from_azure(container_client: Any, blob_name: str, ext: str) -> list[dict]:
    """Azure blob에서 스키마 추론"""
    try:
        if ext == "csv":
            import csv
            import io
            bc = container_client.get_blob_client(blob_name)
            data = bc.download_blob(offset=0, length=8192).readall().decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(data))
            header = next(reader, None)
            if header:
                return [{"name": col.strip(), "type": "TEXT", "nullable": True} for col in header]
        elif ext in ("json", "jsonl"):
            import json
            bc = container_client.get_blob_client(blob_name)
            data = bc.download_blob(offset=0, length=8192).readall().decode("utf-8", errors="ignore")
            first_line = data.strip().split("\n")[0]
            obj = json.loads(first_line)
            if isinstance(obj, dict):
                return [{"name": k, "type": "TEXT", "nullable": True} for k, v in obj.items()]
    except Exception as e:
        logger.warning("Azure 스키마 추론 실패: %s — %s", blob_name, e)
    return [{"name": "data", "type": "TEXT", "nullable": True}]


def _register():
    AdapterFactory.register("azure_blob", AzureBlobAdapter)
    register_manifest(ConnectorManifest(
        engine="azure_blob", display_name="Azure Blob Storage",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="Azure Blob Storage — azure-storage-blob + CSV/JSON 스키마 추론",
    ))

_register()
