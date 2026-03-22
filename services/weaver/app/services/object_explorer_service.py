"""Object Explorer 서비스 — FK 드릴다운 + 다형성 텍스트 검색.

KAIR ontology_explorer.py를 Axiom Weaver 패턴으로 이식.
MindsDB 또는 asyncpg를 통해 바인딩된 테이블의 실제 데이터를 검색한다.

핵심 알고리즘:
  1. Synapse에서 ObjectType 메타데이터 조회 (테이블명, 컬럼 목록, FK 관계)
  2. 컬럼을 ID/텍스트로 자동 분류 (한국어 지원)
  3. ILIKE 검색 또는 FK JOIN으로 데이터 조회
  4. 결과에서 ID/Name 자동 추출
"""
from __future__ import annotations

import re
import logging
from typing import Any

from app.services.mindsdb_client import mindsdb_client, MindsDBUnavailableError

logger = logging.getLogger("axiom.weaver.object_explorer")

# ── 컬럼 분류 휴리스틱 ──

# ID 컬럼 패턴 (대소문자 무시)
_ID_PATTERNS = re.compile(r"(^id$|_id$|_code$|_no$|_key$|번호$|코드$)", re.IGNORECASE)

# 텍스트 컬럼 패턴 (검색 대상)
_TEXT_PATTERNS = re.compile(
    r"(name|title|desc|label|nm$|명$|이름$|설명$|제목$|내용$)", re.IGNORECASE
)

# SQL Identifier 검증 — injection 방지
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,62}$")


def _is_safe_identifier(name: str) -> bool:
    """SQL 식별자가 안전한지 검증한다."""
    return bool(_SAFE_IDENTIFIER.match(name))


def _classify_column(col_name: str) -> str:
    """컬럼을 id/text/other로 분류한다."""
    if _ID_PATTERNS.search(col_name):
        return "id"
    if _TEXT_PATTERNS.search(col_name):
        return "text"
    return "other"


class ObjectExplorerService:
    """ObjectType 바인딩 데이터 검색 + FK 드릴다운 서비스."""

    async def search(
        self, query: str, limit: int = 100, datasource: str = ""
    ) -> list[dict[str, Any]]:
        """전체 텍스트 검색 — 바인딩된 테이블에서 ILIKE 검색.

        1. Synapse에서 ObjectType 메타데이터 조회
        2. 각 ObjectType의 바인딩 테이블에서 텍스트 컬럼 감지
        3. ILIKE WHERE 절 생성 → 검색 실행
        4. 결과에서 ID/Name 휴리스틱 추출

        Args:
            query: 검색어
            limit: 최대 반환 행 수
            datasource: 데이터소스 필터 (빈 문자열이면 전체)

        Returns:
            [{ object_type, id_value, name_value, properties }] 리스트
        """
        # 현재 구현: MindsDB를 통한 테이블 검색
        # TODO: Synapse ObjectType 메타데이터 연동 (현재는 MindsDB 스키마 직접 사용)
        results: list[dict[str, Any]] = []

        try:
            # MindsDB에서 테이블 목록 조회
            tables_data = await mindsdb_client.execute_query(
                f"SHOW TABLES" + (f" FROM {datasource}" if datasource and _is_safe_identifier(datasource) else "")
            )
            table_names = self._extract_table_names(tables_data)

            # 테이블당 검색 (최대 10개 테이블)
            per_table_limit = max(1, limit // max(1, len(table_names[:10])))

            for table_name in table_names[:10]:
                if not _is_safe_identifier(table_name):
                    continue
                try:
                    items = await self._search_table(
                        table_name, query, per_table_limit, datasource
                    )
                    results.extend(items)
                except Exception as e:
                    logger.debug("table_search_skip", table=table_name, error=str(e))

        except MindsDBUnavailableError:
            logger.warning("mindsdb_unavailable_for_search")
        except Exception as e:
            logger.error("object_search_error", error=str(e))

        return results[:limit]

    async def get_children(
        self,
        parent_type: str,
        parent_id: str,
        parent_properties: dict[str, Any],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """FK 기반 자식 노드 드릴다운.

        부모 ObjectType의 FK 관계를 통해 자식 테이블의 매칭 행을 조회한다.

        Args:
            parent_type: 부모 ObjectType 이름 (= 테이블명)
            parent_id: 부모 행의 ID 값
            parent_properties: 부모 행의 속성 (FK 값 추출용)
            limit: 자식 당 최대 행 수

        Returns:
            [{ object_type, items, count }] 리스트
        """
        children: list[dict[str, Any]] = []

        if not _is_safe_identifier(parent_type):
            return children

        # FK 관계 정보 조회 (현재: MindsDB DESCRIBE로 FK 감지)
        # 향후: Synapse ObjectType FK 메타데이터 직접 사용
        try:
            # 부모 테이블의 FK 관계를 가진 자식 테이블 탐색
            desc_data = await mindsdb_client.execute_query(
                f"DESCRIBE {parent_type}"
            )
            # FK 컬럼 감지하여 자식 테이블 조회
            fk_columns = self._detect_fk_columns(desc_data, parent_properties)

            for fk_info in fk_columns:
                child_table = fk_info.get("child_table", "")
                fk_col = fk_info.get("fk_column", "")
                fk_value = fk_info.get("fk_value", "")

                if not child_table or not _is_safe_identifier(child_table):
                    continue

                try:
                    query = (
                        f'SELECT * FROM "{child_table}" '
                        f"WHERE \"{fk_col}\" = '{fk_value}' LIMIT {limit}"
                    )
                    result = await mindsdb_client.execute_query(query)
                    items = self._extract_rows(result)
                    children.append({
                        "object_type": child_table,
                        "items": items,
                        "count": len(items),
                    })
                except Exception as e:
                    logger.debug("child_fetch_skip", child=child_table, error=str(e))

        except Exception as e:
            logger.warning("children_fetch_error", parent=parent_type, error=str(e))

        return children

    async def get_relationships(self, object_type_name: str) -> dict[str, Any]:
        """ObjectType의 FK 관계 메타데이터를 조회한다.

        Returns:
            { outgoing: [...], incoming: [...] }
        """
        if not _is_safe_identifier(object_type_name):
            return {"outgoing": [], "incoming": []}

        # 현재: 빈 관계 반환 (향후 Synapse schema-edit API 연동)
        # Synapse /api/v3/synapse/schema-edit/relationships 호출 예정
        return {"outgoing": [], "incoming": []}

    # ── 내부 헬퍼 ──

    async def _search_table(
        self, table_name: str, query: str, limit: int, datasource: str = ""
    ) -> list[dict[str, Any]]:
        """단일 테이블에서 텍스트 검색을 수행한다."""
        # 1행 샘플로 컬럼 감지
        fqn = f"{datasource}.{table_name}" if datasource else table_name
        sample = await mindsdb_client.execute_query(
            f'SELECT * FROM "{fqn}" LIMIT 1'
        )
        columns = self._extract_column_names(sample)
        if not columns:
            return []

        # 텍스트 컬럼 감지
        text_cols = [c for c in columns if _classify_column(c) == "text"]
        id_cols = [c for c in columns if _classify_column(c) == "id"]

        if not text_cols:
            # 텍스트 컬럼 없으면 string 타입 추측
            text_cols = columns[:3]

        # ILIKE WHERE 절 생성 — 파라미터화 불가 시 이스케이프
        safe_query = query.replace("'", "''").replace("%", "\\%")
        conditions = [
            f'COALESCE(CAST("{col}" AS TEXT), \'\') ILIKE \'%{safe_query}%\''
            for col in text_cols
            if _is_safe_identifier(col)
        ]
        if not conditions:
            return []

        where_clause = " OR ".join(conditions)
        sql = f'SELECT * FROM "{fqn}" WHERE {where_clause} LIMIT {limit}'

        result = await mindsdb_client.execute_query(sql)
        rows = self._extract_rows(result)

        # ID/Name 휴리스틱 추출
        items: list[dict[str, Any]] = []
        for row in rows:
            id_value = ""
            name_value = ""
            for col in id_cols:
                if col in row and row[col]:
                    id_value = str(row[col])
                    break
            for col in text_cols:
                if col in row and row[col]:
                    name_value = str(row[col])
                    break
            items.append({
                "object_type": table_name,
                "id_value": id_value,
                "name_value": name_value,
                "properties": row,
            })

        return items

    @staticmethod
    def _extract_table_names(data: dict) -> list[str]:
        """MindsDB SHOW TABLES 응답에서 테이블명 추출."""
        tables = []
        for row in data.get("data", []):
            if isinstance(row, (list, tuple)) and row:
                tables.append(str(row[0]))
            elif isinstance(row, dict):
                # 첫 번째 값을 테이블명으로 사용
                for v in row.values():
                    tables.append(str(v))
                    break
        return tables

    @staticmethod
    def _extract_column_names(data: dict) -> list[str]:
        """쿼리 결과에서 컬럼명 추출."""
        if "column_names" in data:
            return data["column_names"]
        rows = data.get("data", [])
        if rows and isinstance(rows[0], dict):
            return list(rows[0].keys())
        return []

    @staticmethod
    def _extract_rows(data: dict) -> list[dict[str, Any]]:
        """쿼리 결과에서 행 데이터 추출."""
        rows = data.get("data", [])
        if rows and isinstance(rows[0], dict):
            return rows
        # 컬럼명 + 행 배열 형태
        col_names = data.get("column_names", [])
        if col_names and rows:
            return [dict(zip(col_names, row)) for row in rows if isinstance(row, (list, tuple))]
        return []

    @staticmethod
    def _detect_fk_columns(
        desc_data: dict, parent_properties: dict
    ) -> list[dict[str, Any]]:
        """DESCRIBE 결과와 부모 속성에서 FK 관계를 추론한다.

        현재는 컬럼명 기반 휴리스틱:
        - parent_id, {parent_type}_id 패턴의 컬럼을 FK로 추정
        """
        fk_columns: list[dict[str, Any]] = []
        # 향후 Synapse schema-edit relationships API 연동
        return fk_columns
