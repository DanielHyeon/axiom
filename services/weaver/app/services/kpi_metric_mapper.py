"""KPI metric mapper — match ontology KPIs to query SELECT expressions.

Three-tier matching:
  1. Exact: metric_sql found in query expr
  2. Alias: KPI alias matches query alias
  3. Fuzzy: KPI name substring in expr/alias (last resort)

Includes ``load_kpi_definitions()`` for asyncpg-based loading from the
ontology table.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("weaver.kpi_metric_mapper")


@dataclass
class KpiDefinition:
    """Ontology KPI definition."""
    kpi_id: str
    name: str
    metric_sql: str
    aliases: List[str] = field(default_factory=list)
    table_hint: Optional[str] = None


@dataclass
class KpiMatch:
    kpi_id: str
    match_type: str    # "exact" | "alias" | "fuzzy"
    confidence: float  # 0.0 ~ 1.0
    matched_expr: str


@dataclass
class KpiMapperConfig:
    fuzzy_min_length: int = 4
    fuzzy_confidence: float = 0.3
    alias_confidence: float = 0.7
    exact_confidence: float = 1.0


def _normalize_sql_expr(expr: str) -> str:
    return re.sub(r"\s+", " ", expr.strip().lower())


class KpiMetricMapper:
    """Maps ontology KPI definitions to query select expressions."""

    def __init__(
        self,
        kpi_definitions: List[KpiDefinition],
        config: KpiMapperConfig | None = None,
    ):
        if config is None:
            config = KpiMapperConfig()
        self.definitions = kpi_definitions
        self.config = config
        self._norm_metrics: Dict[str, KpiDefinition] = {}
        self._alias_map: Dict[str, KpiDefinition] = {}
        for kd in kpi_definitions:
            norm = _normalize_sql_expr(kd.metric_sql)
            self._norm_metrics[norm] = kd
            for alias in kd.aliases:
                self._alias_map[alias.lower().strip()] = kd

    def match_select_exprs(
        self,
        select_exprs: List[dict],
    ) -> List[KpiMatch]:
        """Match query SELECT expressions against ontology KPIs.

        Args:
            select_exprs: ``[{"expr": "SUM(o.amount)", "alias": "total_sales"}, ...]``

        Returns:
            List of KpiMatch (may be empty).
        """
        matches: List[KpiMatch] = []
        seen_kpis: Set[str] = set()

        for sel in select_exprs:
            expr = sel.get("expr", "")
            alias = sel.get("alias", "")
            norm_expr = _normalize_sql_expr(expr)
            norm_alias = alias.lower().strip()

            # 1) Exact metric SQL match
            for norm_metric, kd in self._norm_metrics.items():
                if norm_metric in norm_expr or norm_expr in norm_metric:
                    if kd.kpi_id not in seen_kpis:
                        matches.append(KpiMatch(
                            kpi_id=kd.kpi_id,
                            match_type="exact",
                            confidence=self.config.exact_confidence,
                            matched_expr=expr,
                        ))
                        seen_kpis.add(kd.kpi_id)

            # 2) Alias match
            if norm_alias and norm_alias in self._alias_map:
                kd = self._alias_map[norm_alias]
                if kd.kpi_id not in seen_kpis:
                    matches.append(KpiMatch(
                        kpi_id=kd.kpi_id,
                        match_type="alias",
                        confidence=self.config.alias_confidence,
                        matched_expr=alias,
                    ))
                    seen_kpis.add(kd.kpi_id)

            # 3) Fuzzy (substring)
            for kd in self.definitions:
                if kd.kpi_id in seen_kpis:
                    continue
                kpi_name_lower = kd.name.lower()
                if len(kpi_name_lower) < self.config.fuzzy_min_length:
                    continue
                if kpi_name_lower in norm_expr or kpi_name_lower in norm_alias:
                    matches.append(KpiMatch(
                        kpi_id=kd.kpi_id,
                        match_type="fuzzy",
                        confidence=self.config.fuzzy_confidence,
                        matched_expr=expr or alias,
                    ))
                    seen_kpis.add(kd.kpi_id)

        return matches

    def best_match(
        self,
        select_exprs: List[dict],
    ) -> Optional[KpiMatch]:
        """Return highest-confidence match, or None."""
        matches = self.match_select_exprs(select_exprs)
        if not matches:
            return None
        return max(matches, key=lambda m: m.confidence)


async def load_kpi_definitions(
    conn: Any,
    tenant_id: str,
    datasource_id: str,
) -> List[KpiDefinition]:
    """Load KPI definitions from ontology table via asyncpg.

    Returns an empty list if the table does not exist (graceful degradation
    for environments where the ontology module is not yet deployed).
    """
    try:
        rows = await conn.fetch(
            """
            SELECT kpi_id, name, metric_sql, aliases, table_hint
            FROM weaver.ontology_kpi_definitions
            WHERE tenant_id = $1 AND datasource_id = $2
            """,
            tenant_id, datasource_id,
        )
    except Exception as exc:
        # Table may not exist in early deployments
        err_msg = str(exc).lower()
        if "does not exist" in err_msg or "undefined_table" in err_msg:
            logger.info("ontology_kpi_definitions table not found — returning empty list")
            return []
        raise

    definitions: List[KpiDefinition] = []
    for row in rows:
        aliases_raw = row.get("aliases")
        if isinstance(aliases_raw, str):
            import json
            try:
                aliases = json.loads(aliases_raw)
            except (json.JSONDecodeError, TypeError):
                aliases = []
        elif isinstance(aliases_raw, list):
            aliases = aliases_raw
        else:
            aliases = []

        definitions.append(KpiDefinition(
            kpi_id=row["kpi_id"],
            name=row["name"],
            metric_sql=row["metric_sql"],
            aliases=aliases,
            table_hint=row.get("table_hint"),
        ))

    return definitions
