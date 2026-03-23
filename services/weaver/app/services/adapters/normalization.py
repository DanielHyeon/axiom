"""G32: Metadata Normalization Layer — 표준 메타데이터 스키마.

모든 어댑터(네이티브/MindsDB/DDL/코드분석)가 반환하는 메타데이터를
Axiom 시맨틱 카탈로그가 이해할 수 있는 통합 표준 형식으로 변환한다.

설계 원칙:
- 어떤 경로로 데이터를 가져오더라도 StandardMetadata를 거쳐야 한다
- DB별 타입을 Axiom 표준 타입으로 매핑 (TEXT, INTEGER, DECIMAL 등)
- extraction_depth로 메타데이터 깊이 구분 (full/schema_only/shallow)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── 표준 메타데이터 모델 ── #

class StandardColumnMetadata(BaseModel):
    """컬럼 표준 형식"""
    name: str
    data_type: str                    # Axiom 표준 타입 (TEXT, INTEGER, DECIMAL, BOOLEAN 등)
    original_type: str = ""           # 원본 DB 타입 (varchar(100), number(10,2) 등)
    nullable: bool = True
    is_primary_key: bool = False
    description: str | None = None


class StandardTableMetadata(BaseModel):
    """테이블 표준 형식"""
    name: str
    table_type: str = "TABLE"         # TABLE, VIEW, MATERIALIZED_VIEW, COLLECTION, STREAM
    columns: list[StandardColumnMetadata] = Field(default_factory=list)
    row_count: int | None = None      # shallow 추출 시 None
    description: str | None = None
    source_specific: dict = Field(default_factory=dict)  # 어댑터별 고유 속성


class StandardForeignKeyMetadata(BaseModel):
    """FK 관계 표준 형식"""
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str
    constraint_name: str = ""


class StandardSchemaMetadata(BaseModel):
    """스키마 표준 형식"""
    schema_name: str
    tables: list[StandardTableMetadata] = Field(default_factory=list)


class StandardMetadata(BaseModel):
    """모든 어댑터가 반환하는 통합 메타데이터 형식"""
    source_engine: str                # "postgresql", "snowflake", "mindsdb:mongodb" 등
    source_path: str = ""             # 원본 경로 (schema.table 또는 collection.field)
    extraction_depth: Literal["full", "schema_only", "shallow"] = "full"
    schemas: list[StandardSchemaMetadata] = Field(default_factory=list)
    foreign_keys: list[StandardForeignKeyMetadata] = Field(default_factory=list)
    extraction_method: str = "native" # native, mindsdb, ddl_parse, code_analysis
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ── 타입 매핑 테이블 ── #

# DB별 원본 타입 → Axiom 표준 타입 매핑
_TYPE_MAP: dict[str, dict[str, str]] = {
    "postgresql": {
        "integer": "INTEGER", "int": "INTEGER", "int4": "INTEGER", "int8": "INTEGER",
        "bigint": "INTEGER", "smallint": "INTEGER", "serial": "INTEGER", "bigserial": "INTEGER",
        "numeric": "DECIMAL", "decimal": "DECIMAL", "real": "DECIMAL", "double precision": "DECIMAL",
        "float4": "DECIMAL", "float8": "DECIMAL", "money": "DECIMAL",
        "varchar": "TEXT", "character varying": "TEXT", "text": "TEXT", "char": "TEXT",
        "character": "TEXT", "name": "TEXT", "citext": "TEXT",
        "boolean": "BOOLEAN", "bool": "BOOLEAN",
        "date": "DATE", "timestamp": "TIMESTAMP", "timestamp without time zone": "TIMESTAMP",
        "timestamp with time zone": "TIMESTAMP", "timestamptz": "TIMESTAMP",
        "time": "TIME", "interval": "INTERVAL",
        "uuid": "UUID", "json": "JSON", "jsonb": "JSON",
        "bytea": "BINARY", "oid": "INTEGER",
        "array": "ARRAY", "inet": "TEXT", "macaddr": "TEXT",
    },
    "mysql": {
        "int": "INTEGER", "integer": "INTEGER", "tinyint": "INTEGER", "smallint": "INTEGER",
        "mediumint": "INTEGER", "bigint": "INTEGER",
        "decimal": "DECIMAL", "numeric": "DECIMAL", "float": "DECIMAL", "double": "DECIMAL",
        "varchar": "TEXT", "char": "TEXT", "text": "TEXT", "tinytext": "TEXT",
        "mediumtext": "TEXT", "longtext": "TEXT", "enum": "TEXT", "set": "TEXT",
        "boolean": "BOOLEAN", "bool": "BOOLEAN", "bit": "BOOLEAN",
        "date": "DATE", "datetime": "TIMESTAMP", "timestamp": "TIMESTAMP", "time": "TIME",
        "json": "JSON", "blob": "BINARY", "binary": "BINARY", "varbinary": "BINARY",
    },
    "oracle": {
        "number": "DECIMAL", "integer": "INTEGER", "float": "DECIMAL",
        "binary_float": "DECIMAL", "binary_double": "DECIMAL",
        "varchar2": "TEXT", "nvarchar2": "TEXT", "char": "TEXT", "nchar": "TEXT",
        "clob": "TEXT", "nclob": "TEXT", "long": "TEXT",
        "date": "TIMESTAMP", "timestamp": "TIMESTAMP",
        "raw": "BINARY", "blob": "BINARY", "bfile": "BINARY",
    },
    "mssql": {
        "int": "INTEGER", "bigint": "INTEGER", "smallint": "INTEGER", "tinyint": "INTEGER",
        "decimal": "DECIMAL", "numeric": "DECIMAL", "float": "DECIMAL", "real": "DECIMAL",
        "money": "DECIMAL", "smallmoney": "DECIMAL",
        "varchar": "TEXT", "nvarchar": "TEXT", "char": "TEXT", "nchar": "TEXT",
        "text": "TEXT", "ntext": "TEXT", "xml": "TEXT",
        "bit": "BOOLEAN",
        "date": "DATE", "datetime": "TIMESTAMP", "datetime2": "TIMESTAMP",
        "datetimeoffset": "TIMESTAMP", "smalldatetime": "TIMESTAMP", "time": "TIME",
        "uniqueidentifier": "UUID",
        "varbinary": "BINARY", "binary": "BINARY", "image": "BINARY",
    },
    # Sprint 2: DW + 클라우드 스토리지 어댑터 타입 매핑
    "snowflake": {
        "number": "DECIMAL", "decimal": "DECIMAL", "numeric": "DECIMAL",
        "int": "INTEGER", "integer": "INTEGER", "bigint": "INTEGER", "smallint": "INTEGER",
        "tinyint": "INTEGER", "byteint": "INTEGER", "float": "DECIMAL", "float4": "DECIMAL",
        "float8": "DECIMAL", "double": "DECIMAL", "double precision": "DECIMAL", "real": "DECIMAL",
        "varchar": "TEXT", "char": "TEXT", "character": "TEXT", "string": "TEXT", "text": "TEXT",
        "binary": "BINARY", "varbinary": "BINARY",
        "boolean": "BOOLEAN",
        "date": "DATE", "datetime": "TIMESTAMP", "time": "TIME",
        "timestamp": "TIMESTAMP", "timestamp_ltz": "TIMESTAMP", "timestamp_ntz": "TIMESTAMP",
        "timestamp_tz": "TIMESTAMP",
        "variant": "JSON", "object": "JSON", "array": "ARRAY",
    },
    "bigquery": {
        "string": "TEXT", "bytes": "BINARY",
        "integer": "INTEGER", "int64": "INTEGER",
        "float": "DECIMAL", "float64": "DECIMAL", "numeric": "DECIMAL", "bignumeric": "DECIMAL",
        "boolean": "BOOLEAN", "bool": "BOOLEAN",
        "timestamp": "TIMESTAMP", "date": "DATE", "time": "TIME", "datetime": "TIMESTAMP",
        "geography": "TEXT", "json": "JSON",
        "record": "JSON", "struct": "JSON",
    },
    "clickhouse": {
        "uint8": "INTEGER", "uint16": "INTEGER", "uint32": "INTEGER", "uint64": "INTEGER",
        "int8": "INTEGER", "int16": "INTEGER", "int32": "INTEGER", "int64": "INTEGER",
        "float32": "DECIMAL", "float64": "DECIMAL", "decimal": "DECIMAL",
        "string": "TEXT", "fixedstring": "TEXT", "uuid": "UUID",
        "date": "DATE", "date32": "DATE", "datetime": "TIMESTAMP", "datetime64": "TIMESTAMP",
        "enum8": "TEXT", "enum16": "TEXT",
        "array": "ARRAY", "tuple": "JSON", "map": "JSON",
        "nullable": "TEXT",  # Nullable(X)는 내부 타입으로 분리 파싱 필요 — 기본 TEXT
        "bool": "BOOLEAN",
    },
    "redshift": {
        # Redshift는 PG 호환이므로 postgresql 매핑 재사용
        "integer": "INTEGER", "int": "INTEGER", "int4": "INTEGER", "int8": "INTEGER",
        "bigint": "INTEGER", "smallint": "INTEGER",
        "numeric": "DECIMAL", "decimal": "DECIMAL", "real": "DECIMAL",
        "double precision": "DECIMAL", "float": "DECIMAL", "float4": "DECIMAL", "float8": "DECIMAL",
        "varchar": "TEXT", "character varying": "TEXT", "text": "TEXT", "char": "TEXT",
        "boolean": "BOOLEAN", "bool": "BOOLEAN",
        "date": "DATE", "timestamp": "TIMESTAMP", "timestamptz": "TIMESTAMP",
        "time": "TIME", "timetz": "TIME",
        "super": "JSON",
    },
    # 파일 스토리지는 추론 결과가 이미 Axiom 표준 타입이므로 매핑 불필요
    "s3": {},
    "gcs": {},
    "azure_blob": {},
    # Sprint 4: API/SaaS + NoSQL 어댑터
    "mongodb": {
        "string": "TEXT", "int": "INTEGER", "long": "INTEGER",
        "double": "DECIMAL", "decimal": "DECIMAL",
        "bool": "BOOLEAN", "date": "TIMESTAMP", "timestamp": "TIMESTAMP",
        "objectId": "UUID", "binData": "BINARY", "array": "ARRAY",
        "object": "JSON", "regex": "TEXT", "null": "TEXT",
    },
    "redis": {
        # Redis는 모두 문자열 저장 — 추론 결과가 이미 Axiom 표준 타입
        "string": "TEXT", "hash": "JSON", "list": "ARRAY",
        "set": "ARRAY", "zset": "JSON",
    },
    # REST API / GraphQL은 JSON 추론 결과가 이미 표준 타입
    "rest_api": {},
    "graphql": {},
    # Sprint 16: Kafka + 벡터 DB
    "kafka": {},
    "vector_db": {},
}


class MetadataNormalizer:
    """어댑터별 원시 메타데이터 → StandardMetadata 변환.

    기존 core/adapters.py의 extract_schema() 반환값을 StandardMetadata로 정규화한다.
    """

    def normalize_type(self, engine: str, original_type: str) -> str:
        """DB별 타입을 Axiom 표준 타입으로 변환"""
        engine_map = _TYPE_MAP.get(engine.lower(), {})
        # 괄호 제거 (varchar(100) → varchar)
        base_type = original_type.lower().split("(")[0].strip()
        return engine_map.get(base_type, "TEXT")  # 기본값: TEXT

    def normalize_from_raw(
        self,
        engine: str,
        raw_schema: dict[str, Any],
        extraction_method: str = "native",
    ) -> StandardMetadata:
        """기존 core/adapters.py 형식 → StandardMetadata 변환.

        raw_schema 형식 (기존): {engine, schema, tables: [{name, columns}], foreign_keys: [...]}
        """
        schema_name = raw_schema.get("schema", "public")
        raw_tables = raw_schema.get("tables", [])
        raw_fks = raw_schema.get("foreign_keys", [])

        # 테이블 정규화
        tables: list[StandardTableMetadata] = []
        for t in raw_tables:
            if not isinstance(t, dict):
                continue
            columns: list[StandardColumnMetadata] = []
            for c in t.get("columns", []):
                if not isinstance(c, dict):
                    continue
                original = str(c.get("type", "text"))
                columns.append(StandardColumnMetadata(
                    name=str(c.get("name", "")),
                    data_type=self.normalize_type(engine, original),
                    original_type=original,
                    nullable=bool(c.get("nullable", True)),
                ))
            tables.append(StandardTableMetadata(
                name=str(t.get("name", "")),
                columns=columns,
                row_count=t.get("row_count"),
            ))

        # FK 정규화
        fks: list[StandardForeignKeyMetadata] = []
        for fk in raw_fks:
            if not isinstance(fk, dict):
                continue
            fks.append(StandardForeignKeyMetadata(
                source_schema=str(fk.get("source_schema", schema_name)),
                source_table=str(fk.get("source_table", "")),
                source_column=str(fk.get("source_column", "")),
                target_schema=str(fk.get("target_schema", "")),
                target_table=str(fk.get("target_table", "")),
                target_column=str(fk.get("target_column", "")),
                constraint_name=str(fk.get("constraint_name", "")),
            ))

        return StandardMetadata(
            source_engine=engine,
            source_path=schema_name,
            schemas=[StandardSchemaMetadata(schema_name=schema_name, tables=tables)],
            foreign_keys=fks,
            extraction_method=extraction_method,
        )
