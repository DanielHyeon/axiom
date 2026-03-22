"""
시멘틱 컴파일러 — 계약 검증 + SQL 뷰 템플릿 생성

시멘틱 계약(엔티티, 지표, 차원, 조인, 그레인, 품질)을 검증하고,
각 지표에 대한 실행 가능한 SQL SELECT 템플릿을 생성한다.

이 컴파일러는 SQL을 직접 실행하지 않는다 (Control Plane).
생성된 SQL 템플릿은 Weaver 등 Data Plane이 실행할 때 참조한다.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.services.semantic_store import SemanticStore

logger = structlog.get_logger()


class CompileIssue:
    """컴파일 검증 이슈"""
    __slots__ = ("severity", "code", "message", "target_id")

    def __init__(self, severity: str, code: str, message: str, target_id: str | None = None):
        self.severity = severity
        self.code = code
        self.message = message
        self.target_id = target_id

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "code": self.code, "message": self.message, "target_id": self.target_id}


class SemanticCompiler:
    """시멘틱 계약을 검증하고 SQL 템플릿을 생성하는 컴파일러"""

    def __init__(self, store: SemanticStore):
        self._store = store

    # ── 엔티티 단위 컴파일 ──

    def compile_entity(self, tenant_id: str, entity_id: str) -> dict[str, Any]:
        """엔티티와 연결된 지표/차원/조인/그레인을 모두 검증하고 SQL을 생성한다."""
        entity = self._store.get_entity(tenant_id, entity_id)
        if not entity:
            return {"valid": False, "sql_template": None, "issues": [
                CompileIssue("error", "ENTITY_NOT_FOUND", f"entity_id '{entity_id}'를 찾을 수 없습니다").to_dict()
            ], "metadata": {}}

        issues: list[dict[str, Any]] = []

        # 1. 온톨로지 바인딩 검증
        if not entity.get("bound_concept_id"):
            issues.append(CompileIssue("warning", "MISSING_BINDING",
                "엔티티가 온톨로지 개념에 바인딩되지 않았습니다 (publish 시 필수)", entity_id).to_dict())

        # 2. 그레인 존재 검증
        grains = self._store.list_grain_contracts(tenant_id, entity_id=entity_id, limit=100)
        if not grains:
            issues.append(CompileIssue("warning", "NO_GRAIN",
                "그레인 계약이 정의되지 않았습니다 — 행 중복 위험", entity_id).to_dict())

        # 3. 지표 검증
        measures = self._store.list_measures(tenant_id, entity_id=entity_id, limit=500)
        for m in measures:
            m_issues = self._validate_measure(tenant_id, m)
            issues.extend(m_issues)

        # 4. 차원 검증
        dimensions = self._store.list_dimensions(tenant_id, entity_id=entity_id, limit=500)
        for d in dimensions:
            if not d.get("sql_expression", "").strip():
                issues.append(CompileIssue("error", "EMPTY_SQL_EXPRESSION",
                    f"차원 '{d['dimension_id']}'의 sql_expression이 비어있습니다", d["dimension_id"]).to_dict())

        # 5. 조인 검증 — 이 엔티티가 참여하는 조인
        joins = self._store.list_join_contracts(tenant_id, limit=500)
        entity_joins = [j for j in joins if j.get("left_entity_id") == entity_id or j.get("right_entity_id") == entity_id]
        for j in entity_joins:
            j_issues = self._validate_join(tenant_id, j)
            issues.extend(j_issues)

        # 6. SQL 템플릿 생성 (에러가 없을 때만)
        has_errors = any(i["severity"] == "error" for i in issues)
        sql_template = None
        if not has_errors and measures:
            sql_template = self._generate_entity_sql(entity, measures, dimensions, grains, entity_joins)

        return {
            "valid": not has_errors,
            "sql_template": sql_template,
            "issues": issues,
            "metadata": {
                "entity_id": entity_id,
                "measure_count": len(measures),
                "dimension_count": len(dimensions),
                "join_count": len(entity_joins),
                "grain_count": len(grains),
            },
        }

    # ── 지표 단위 컴파일 ──

    def compile_measure(self, tenant_id: str, measure_id: str) -> dict[str, Any]:
        """단일 지표의 검증 + SQL 생성"""
        measure = self._store.get_measure(tenant_id, measure_id)
        if not measure:
            return {"valid": False, "sql_template": None, "issues": [
                CompileIssue("error", "MEASURE_NOT_FOUND", f"measure_id '{measure_id}'를 찾을 수 없습니다").to_dict()
            ], "metadata": {}}

        entity = self._store.get_entity(tenant_id, measure["entity_id"])
        if not entity:
            return {"valid": False, "sql_template": None, "issues": [
                CompileIssue("error", "ENTITY_NOT_FOUND",
                    f"지표가 참조하는 entity_id '{measure['entity_id']}'를 찾을 수 없습니다", measure_id).to_dict()
            ], "metadata": {}}

        issues = self._validate_measure(tenant_id, measure)
        has_errors = any(i["severity"] == "error" for i in issues)
        sql_template = None
        if not has_errors:
            sql_template = self._generate_measure_sql(entity, measure)

        return {
            "valid": not has_errors,
            "sql_template": sql_template,
            "issues": issues,
            "metadata": {"measure_id": measure_id, "entity_id": measure["entity_id"]},
        }

    # ── 내부 검증 메서드 ──

    def _validate_measure(self, tenant_id: str, measure: dict[str, Any]) -> list[dict[str, Any]]:
        """지표 계약 검증 — 바인딩, SQL식, 비율형 검증"""
        issues: list[dict[str, Any]] = []
        mid = measure.get("measure_id", "?")

        if not measure.get("sql_expression", "").strip():
            issues.append(CompileIssue("error", "EMPTY_SQL_EXPRESSION",
                f"지표 '{mid}'의 sql_expression이 비어있습니다", mid).to_dict())

        if not measure.get("bound_concept_id"):
            issues.append(CompileIssue("warning", "MISSING_BINDING",
                f"지표 '{mid}'가 온톨로지 개념에 바인딩되지 않았습니다", mid).to_dict())

        # 비율형(ratio/rate) 지표는 분자/분모 지표 필요
        if measure.get("measure_type") in ("ratio", "rate"):
            if not measure.get("numerator_measure_id") or not measure.get("denominator_measure_id"):
                issues.append(CompileIssue("error", "RATIO_MISSING_PARTS",
                    f"비율형 지표 '{mid}'는 numerator/denominator 지표가 필요합니다", mid).to_dict())

        return issues

    def _validate_join(self, tenant_id: str, join: dict[str, Any]) -> list[dict[str, Any]]:
        """조인 계약 검증 — fanout 위험, 양쪽 엔티티 존재"""
        issues: list[dict[str, Any]] = []
        jid = join.get("join_id", "?")

        # fanout 위험 경고
        fanout = float(join.get("fanout_risk_score") or 0)
        if fanout >= 0.7:
            issues.append(CompileIssue("warning", "FANOUT_RISK",
                f"조인 '{jid}'의 fanout 위험 점수가 높습니다 ({fanout})", jid).to_dict())

        # 조인 조건 비어있는지
        if not (join.get("join_condition") or "").strip():
            issues.append(CompileIssue("error", "EMPTY_JOIN_CONDITION",
                f"조인 '{jid}'의 join_condition이 비어있습니다", jid).to_dict())

        return issues

    # ── SQL 생성 ──

    def _generate_measure_sql(self, entity: dict[str, Any], measure: dict[str, Any]) -> str:
        """단일 지표에 대한 SELECT SQL 생성"""
        source = entity.get("physical_source_ref", "UNKNOWN_TABLE")
        expr = measure.get("sql_expression", "NULL")
        alias = measure.get("measure_id", "metric").replace(".", "_")

        # 집계 함수 래핑
        mtype = measure.get("measure_type", "sum")
        if mtype == "distinct_count":
            select_expr = f"COUNT(DISTINCT {expr})"
        elif mtype in ("sum", "count", "avg"):
            select_expr = f"{mtype.upper()}({expr})"
        elif mtype == "percentile":
            select_expr = f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {expr})"
        elif mtype in ("ratio", "rate"):
            # 비율형은 분자/분모를 참조 — 여기선 placeholder
            select_expr = f"({expr})  /* ratio: numerator/denominator */"
        else:
            # derived 또는 기타 — sql_expression 그대로 사용
            select_expr = expr

        # 필터 조건
        where = ""
        filter_expr = (measure.get("filter_expression") or "").strip()
        if filter_expr:
            where = f"\nWHERE {filter_expr}"

        return f"-- 시멘틱 지표: {measure.get('name', alias)}\n-- 버전: {measure.get('version', 1)}\nSELECT\n  {select_expr} AS {alias}{where}\nFROM {source}"

    def _generate_entity_sql(
        self,
        entity: dict[str, Any],
        measures: list[dict[str, Any]],
        dimensions: list[dict[str, Any]],
        grains: list[dict[str, Any]],
        joins: list[dict[str, Any]],
    ) -> str:
        """엔티티 전체에 대한 VIEW SQL 생성 (지표 + 차원 포함)"""
        source = entity.get("physical_source_ref", "UNKNOWN_TABLE")
        entity_alias = "t0"
        lines = [f"-- 시멘틱 엔티티 뷰: {entity.get('entity_id', 'unknown')}", f"-- 물리 소스: {source}", "SELECT"]

        select_parts: list[str] = []

        # 차원 컬럼
        for d in dimensions:
            expr = d.get("sql_expression", d.get("name", "?"))
            alias = d.get("dimension_id", "dim").replace(".", "_")
            select_parts.append(f"  {expr} AS {alias}")

        # 지표 컬럼
        for m in measures:
            expr = m.get("sql_expression", "NULL")
            alias = m.get("measure_id", "metric").replace(".", "_")
            mtype = m.get("measure_type", "sum")
            if mtype == "distinct_count":
                agg = f"COUNT(DISTINCT {expr})"
            elif mtype in ("sum", "count", "avg"):
                agg = f"{mtype.upper()}({expr})"
            else:
                agg = expr
            select_parts.append(f"  {agg} AS {alias}")

        if not select_parts:
            select_parts.append("  *")
        lines.append(",\n".join(select_parts))
        lines.append(f"FROM {source} AS {entity_alias}")

        # 조인 절
        for idx, j in enumerate(joins, 1):
            other_entity_id = j["right_entity_id"] if j["left_entity_id"] == entity["entity_id"] else j["left_entity_id"]
            other_entity = self._store.get_entity(entity.get("tenant_id", ""), other_entity_id)
            other_source = other_entity.get("physical_source_ref", "UNKNOWN") if other_entity else "UNKNOWN"
            join_alias = f"t{idx}"
            jtype = j.get("join_type", "LEFT")
            condition = j.get("join_condition", "TRUE")
            lines.append(f"{jtype} JOIN {other_source} AS {join_alias} ON {condition}")

        # GROUP BY (차원이 있으면)
        if dimensions and measures:
            group_indices = ", ".join(str(i + 1) for i in range(len(dimensions)))
            lines.append(f"GROUP BY {group_indices}")

        return "\n".join(lines)
