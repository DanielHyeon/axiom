"""G02: BigQuery 어댑터 — supported 등급.

Google BigQuery 프로젝트/데이터셋 기반 스키마 탐색.
google-cloud-bigquery 클라이언트.
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

logger = logging.getLogger("axiom.weaver.adapters.bigquery")

try:
    from google.cloud import bigquery  # type: ignore
    HAS_BIGQUERY = True
except ImportError:
    HAS_BIGQUERY = False


class BigQueryAdapter(DatabaseAdapter):
    """BigQuery 어댑터 — project_id + dataset 기반"""

    engine = "bigquery"

    def _validate(self) -> None:
        if not HAS_BIGQUERY:
            raise ImportError("pip install google-cloud-bigquery")

    def _get_client(self) -> Any:
        """BigQuery 클라이언트 생성 — credentials_json 또는 기본 인증"""
        project = self.connection.get("project_id", "")
        creds_json = self.connection.get("credentials_json", "")
        if creds_json:
            import json
            from google.oauth2 import service_account  # type: ignore
            info = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
            credentials = service_account.Credentials.from_service_account_info(info)
            return bigquery.Client(project=project, credentials=credentials)
        return bigquery.Client(project=project)

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            def _test():
                client = self._get_client()
                try:
                    list(client.list_datasets(max_results=1))
                finally:
                    client.close()
            await asyncio.to_thread(_test)
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """BigQuery에서 스키마 = 데이터셋"""
        self._validate()
        dataset = self.connection.get("dataset", "")
        if dataset:
            return [dataset]
        def _fetch():
            client = self._get_client()
            try:
                return [ds.dataset_id for ds in client.list_datasets()]
            finally:
                client.close()
        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        project = self.connection.get("project_id", "")
        def _fetch():
            client = self._get_client()
            try:
                dataset_ref = f"{project}.{schema}" if project else schema
                tables_list = list(client.list_tables(dataset_ref))
            result = []
            for tbl in tables_list:
                full_table = client.get_table(tbl.reference)
                columns = []
                for field in full_table.schema:
                    columns.append({
                        "name": field.name,
                        "type": field.field_type,
                        "nullable": field.mode != "REQUIRED",
                    })
                entry: dict[str, Any] = {"name": tbl.table_id, "columns": columns}
                if include_row_counts:
                    entry["row_count"] = full_table.num_rows
                result.append(entry)
                return result
            finally:
                client.close()
        return await asyncio.to_thread(_fetch)

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """BigQuery는 네이티브 FK를 지원하지 않음 (2024년부터 preview)"""
        # BigQuery FK는 아직 preview 단계 — 빈 목록 반환
        return []


def _register():
    AdapterFactory.register("bigquery", BigQueryAdapter)
    register_manifest(ConnectorManifest(
        engine="bigquery", display_name="Google BigQuery",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW, ConnectorCapability.STREAMING_EXTRACT,
        ],
        credential_modes=[CredentialMode.SERVICE_ACCOUNT, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.SUPPORTED, version="0.1.0",
        description="Google BigQuery — google-cloud-bigquery",
    ))

_register()
