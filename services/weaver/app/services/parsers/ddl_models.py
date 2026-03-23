"""G04: DDL 파서 모델 — ParsedTable, ParsedColumn, ParsedForeignKey.

DDL 정적 파싱 결과를 담는 Pydantic 모델.
StandardMetadata로 변환하거나 Neo4j에 직접 저장할 수 있다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ParsedColumn(BaseModel):
    """파싱된 컬럼 정의"""
    name: str
    data_type: str                    # 원본 DDL 타입 (예: VARCHAR(100))
    nullable: bool = True
    is_primary_key: bool = False
    default_value: str | None = None
    comment: str | None = None        # COMMENT ON COLUMN 값
    # G01b: 방언별 확장 속성
    is_identity: bool = False         # T-SQL IDENTITY / Snowflake AUTOINCREMENT
    is_computed: bool = False         # T-SQL 계산 컬럼 (AS expression)
    computed_expression: str = ""     # 계산식
    is_auto_increment: bool = False   # MySQL AUTO_INCREMENT
    column_length: int | None = None  # @Column(length=255)
    is_unique: bool = False           # @Column(unique=true)


class ParsedPrimaryKey(BaseModel):
    """파싱된 PK 제약조건"""
    constraint_name: str = ""
    columns: list[str] = Field(default_factory=list)


class ParsedForeignKey(BaseModel):
    """파싱된 FK 제약조건"""
    constraint_name: str = ""
    source_columns: list[str] = Field(default_factory=list)
    target_schema: str = ""
    target_table: str = ""
    target_columns: list[str] = Field(default_factory=list)
    on_delete: str = ""               # CASCADE, SET NULL, RESTRICT 등
    on_update: str = ""


class ParsedIndex(BaseModel):
    """파싱된 인덱스 정의"""
    index_name: str = ""
    columns: list[str] = Field(default_factory=list)
    is_unique: bool = False
    include_columns: list[str] = Field(default_factory=list)  # G01b: INCLUDE (col) 커버링 인덱스


class ParsedTable(BaseModel):
    """파싱된 테이블 정의"""
    schema_name: str = ""             # DDL에 스키마 명시된 경우
    table_name: str
    columns: list[ParsedColumn] = Field(default_factory=list)
    primary_key: ParsedPrimaryKey | None = None
    foreign_keys: list[ParsedForeignKey] = Field(default_factory=list)
    indexes: list[ParsedIndex] = Field(default_factory=list)
    comment: str | None = None        # COMMENT ON TABLE 값
    if_not_exists: bool = False
    # G01b: 방언별 확장 속성
    dialect_info: dict = Field(default_factory=dict)  # {"engine": "InnoDB", "cluster_by": [...]}


class ParsedView(BaseModel):
    """G01b: 파싱된 뷰 정의 (CREATE VIEW / MATERIALIZED VIEW)"""
    schema_name: str = ""
    view_name: str
    is_materialized: bool = False
    select_sql: str = ""              # AS 뒤의 SELECT 전체
    columns: list[str] = Field(default_factory=list)  # 컬럼 리스트 (명시된 경우)
    source_tables: list[str] = Field(default_factory=list)  # 뷰가 참조하는 테이블들
    comment: str | None = None


class DDLParseResult(BaseModel):
    """전체 DDL 파싱 결과"""
    tables: list[ParsedTable] = Field(default_factory=list)
    views: list[ParsedView] = Field(default_factory=list)  # G01b: 뷰 정의
    indexes: list[ParsedIndex] = Field(default_factory=list)  # G01b: 독립 인덱스
    errors: list[str] = Field(default_factory=list)  # 파싱 실패한 구문
    source_file: str = ""
    dialect: str = "postgresql"       # postgresql, oracle, mysql, tsql, snowflake
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def view_count(self) -> int:
        return len(self.views)

    @property
    def error_count(self) -> int:
        return len(self.errors)
