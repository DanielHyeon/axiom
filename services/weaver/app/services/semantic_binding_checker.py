"""G33b 고도화: L2 시맨틱 바인딩 실연동 — 드리프트 영향도 분석.

SSDD Stage 2를 MVP(impact_score=0)에서 실연동으로 고도화:
- 변경된 테이블/컬럼이 L2 시맨틱 계약에서 참조되는지 확인
- 영향 받는 SemanticEntity, Measure, Dimension, JoinContract, ContextPack 산출
- Impact Score = total_l2_affected + cache_keys_affected * 2

조회 경로: Synapse HTTP API → PostgreSQL 직접 조회 → 폴백(impact=0)
G33b 고도화: 컬럼 수준 + 차원 + 조인 계약 + ContextPack 영향도
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, Field

logger = logging.getLogger("axiom.weaver.semantic_binding_checker")


# ── 모델 ── #

class ImpactResult(BaseModel):
    """L2 바인딩 영향도 분석 결과"""
    table_name: str = ""
    column_name: str | None = None
    # 영향 받는 L2 자산
    affected_entities: list[str] = Field(default_factory=list)  # SemanticEntity IDs
    affected_measures: list[str] = Field(default_factory=list)  # SemanticMeasure 이름
    affected_dimensions: list[str] = Field(default_factory=list)  # SemanticDimension 이름
    affected_joins: list[str] = Field(default_factory=list)  # JoinContract IDs
    affected_context_packs: list[str] = Field(default_factory=list)
    # 영향 수치
    total_l2_affected: int = 0
    cache_keys_affected: int = 0
    impact_score: int = 0  # total_l2_affected + cache_keys_affected * 2 (ContextPack 가중)

    @property
    def has_impact(self) -> bool:
        return self.impact_score > 0

    @property
    def is_breaking(self) -> bool:
        """파괴적 변경 여부 — L2 참조가 1개라도 있으면 breaking"""
        return self.total_l2_affected > 0

    @property
    def severity_recommendation(self) -> str:
        """G33b: 영향도 기반 조치 권고 — safe / review / block"""
        if self.impact_score == 0:
            return "safe"
        if self.impact_score <= 3:
            return "review"
        return "block"


class SemanticBindingChecker:
    """L2 시맨틱 바인딩 검사기.

    변경된 테이블/컬럼이 시맨틱 계약 계층(L2)에서 참조되는지 확인한다.

    조회 경로 (우선순위):
    1. Synapse HTTP API: GET /api/v3/synapse/semantic/impact/{type}/{id}
    2. PostgreSQL 직접 조회: entity + measure + dimension + join + context_pack
    3. 폴백: impact_score = 0 (MVP 동작 유지)
    """

    # G33b: TTL 캐시 (5분)
    _CACHE_TTL = 300
    # C1 수정: 테이블명 안전 패턴 (SQL 식별자)
    _SAFE_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]{0,127}$')

    @staticmethod
    def _escape_like(value: str) -> str:
        """C2 수정: LIKE 메타문자 이스케이프 — SQL injection 방지"""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def __init__(self) -> None:
        # (result, timestamp) 형태의 TTL 캐시
        self._binding_cache: dict[str, tuple[ImpactResult, float]] = {}

    async def check_impact(
        self,
        datasource_name: str,
        schema_name: str,
        table_name: str,
        column_name: str | None = None,
        tenant_id: str = "",
    ) -> ImpactResult:
        """테이블/컬럼 변경의 L2 영향도 분석.

        1. Synapse API 호출 시도
        2. 실패 시 PostgreSQL 직접 조회 시도
        3. 모두 실패 시 폴백 (impact=0)
        """
        cache_key = f"{tenant_id}:{datasource_name}:{schema_name}.{table_name}"
        if column_name:
            cache_key += f".{column_name}"

        # G33b: TTL 캐시 확인 (5분)
        now = time.monotonic()
        cached = self._binding_cache.get(cache_key)
        if cached and (now - cached[1]) < self._CACHE_TTL:
            return cached[0]

        # 1. Synapse API 호출
        result = await self._check_via_synapse_api(
            datasource_name, schema_name, table_name, column_name, tenant_id,
        )

        if result is None:
            # 2. PostgreSQL 직접 조회 (G33b 고도화: 전체 L2 계층)
            result = await self._check_via_postgres(
                datasource_name, schema_name, table_name, column_name, tenant_id,
            )

        if result is None:
            # 3. 폴백
            result = ImpactResult(table_name=table_name, column_name=column_name)

        # M4 수정: eviction을 insert 전에 실행 — 무한 성장 방지
        if len(self._binding_cache) >= 500:
            self.purge_expired()
            if len(self._binding_cache) >= 500:
                oldest = min(self._binding_cache, key=lambda k: self._binding_cache[k][1])
                del self._binding_cache[oldest]
        self._binding_cache[cache_key] = (result, now)

        return result

    async def _check_via_synapse_api(
        self,
        datasource_name: str,
        schema_name: str,
        table_name: str,
        column_name: str | None,
        tenant_id: str,
    ) -> ImpactResult | None:
        """Synapse HTTP API로 영향도 조회.

        GET /api/v3/synapse/semantic/impact/table/{table_name}
        """
        try:
            import httpx
            # C1 수정: table_name SSRF 방지 — 안전한 식별자만 허용
            if not self._SAFE_IDENT.match(table_name):
                logger.warning("잘못된 table_name (API 호출 거부): %s", table_name[:50])
                return None
            url = f"http://synapse-svc:8003/api/v3/synapse/semantic/impact/table/{quote(table_name, safe='')}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers={"X-Tenant-Id": tenant_id})
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    entities = data.get("affected_entities", [])
                    measures = data.get("affected_measures", [])
                    dimensions = data.get("affected_dimensions", [])
                    joins = data.get("affected_joins", [])
                    total = len(entities) + len(measures) + len(dimensions) + len(joins)

                    return ImpactResult(
                        table_name=table_name,
                        column_name=column_name,
                        affected_entities=entities,
                        affected_measures=measures,
                        affected_dimensions=dimensions,
                        affected_joins=joins,
                        total_l2_affected=total,
                        impact_score=total,
                    )
        except Exception as e:
            logger.debug("Synapse API 호출 실패 (폴백): %s", e)

        return None

    async def _check_via_postgres(
        self,
        datasource_name: str,
        schema_name: str,
        table_name: str,
        column_name: str | None,
        tenant_id: str,
    ) -> ImpactResult | None:
        """G33b 고도화: PostgreSQL synapse 스키마 전체 L2 계층 조회.

        조회 대상:
        1. semantic_entities — 테이블 직접 참조
        2. semantic_measures — sql_expression에 테이블/컬럼 포함
        3. semantic_dimensions — sql_expression에 테이블/컬럼 포함
        4. join_contracts — left/right 엔티티가 해당 테이블 참조
        5. context_packs — 영향 받는 엔티티를 참조하는 ContextPack
        """
        try:
            import asyncpg  # type: ignore
            from app.core.config import settings

            dsn = getattr(settings, "database_url", "").replace("+asyncpg", "")
            if not dsn:
                return None

            conn = await asyncpg.connect(dsn=dsn, timeout=5.0)
            try:
                # 1. 시맨틱 엔티티 — 테이블 직접 매핑
                entity_rows = await conn.fetch(
                    "SELECT id, name FROM synapse.semantic_entities "
                    "WHERE physical_table_name = $1 AND tenant_id = $2",
                    table_name, tenant_id,
                )
                entities = [str(r["id"]) for r in entity_rows]
                entity_ids = [r["id"] for r in entity_rows]

                # 2. 시맨틱 측정 — sql_expression에 테이블 또는 컬럼 참조
                # C2 수정: LIKE 메타문자 이스케이프
                safe_name = self._escape_like(column_name) if column_name else self._escape_like(table_name)
                measure_pattern = f"%{safe_name}%"
                measure_rows = await conn.fetch(
                    "SELECT name FROM synapse.semantic_measures "
                    "WHERE sql_expression LIKE $1 ESCAPE '\\' AND tenant_id = $2",
                    measure_pattern, tenant_id,
                )
                measures = [r["name"] for r in measure_rows]

                # 3. 시맨틱 차원 — sql_expression에 테이블/컬럼 참조
                dim_rows = await conn.fetch(
                    "SELECT name FROM synapse.semantic_dimensions "
                    "WHERE sql_expression LIKE $1 ESCAPE '\\' AND tenant_id = $2",
                    measure_pattern, tenant_id,
                )
                dimensions = [r["name"] for r in dim_rows]

                # 4. 조인 계약 — 엔티티 ID로 영향 조회
                joins: list[str] = []
                if entity_ids:
                    # 엔티티 ID가 left 또는 right에 있는 조인 계약
                    join_rows = await conn.fetch(
                        "SELECT id FROM synapse.join_contracts "
                        "WHERE (left_entity_id = ANY($1) OR right_entity_id = ANY($2)) "
                        "AND tenant_id = $3",
                        entity_ids, entity_ids, tenant_id,
                    )
                    joins = [str(r["id"]) for r in join_rows]

                    # 컬럼 변경이면 join_condition도 검사
                    if column_name:
                        safe_col = self._escape_like(column_name)
                        col_join_rows = await conn.fetch(
                            "SELECT id FROM synapse.join_contracts "
                            "WHERE join_condition LIKE $1 ESCAPE '\\' AND tenant_id = $2",
                            f"%{safe_col}%", tenant_id,
                        )
                        joins.extend(str(r["id"]) for r in col_join_rows)
                        joins = list(dict.fromkeys(joins))  # 중복 제거

                # 5. ContextPack 무효화 — 영향 받는 엔티티를 참조하는 팩
                context_packs: list[str] = []
                if entity_ids:
                    # context_packs 테이블이 존재하면 조회
                    try:
                        cp_rows = await conn.fetch(
                            "SELECT id FROM synapse.context_packs "
                            "WHERE entity_ids && $1 AND tenant_id = $2",
                            entity_ids, tenant_id,
                        )
                        context_packs = [str(r["id"]) for r in cp_rows]
                    except Exception:
                        # 테이블 미존재 또는 스키마 불일치 — 무시
                        pass

                # Impact Score 계산: L2 자산 수 + ContextPack × 2 (가중치)
                total_l2 = len(entities) + len(measures) + len(dimensions) + len(joins)
                cache_keys = len(context_packs)
                score = total_l2 + cache_keys * 2

                return ImpactResult(
                    table_name=table_name,
                    column_name=column_name,
                    affected_entities=entities,
                    affected_measures=measures,
                    affected_dimensions=dimensions,
                    affected_joins=joins,
                    affected_context_packs=context_packs,
                    total_l2_affected=total_l2,
                    cache_keys_affected=cache_keys,
                    impact_score=score,
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.debug("PostgreSQL 직접 조회 실패 (폴백): %s", e)

        return None

    def invalidate_cache(self, table_name: str = "", tenant_id: str = "") -> int:
        """바인딩 캐시 무효화 (G33b: TTL 캐시 대응)"""
        if not table_name:
            count = len(self._binding_cache)
            self._binding_cache.clear()
            return count

        to_remove = [
            k for k in self._binding_cache
            if table_name in k and (not tenant_id or k.startswith(f"{tenant_id}:"))
        ]
        for k in to_remove:
            del self._binding_cache[k]
        return len(to_remove)

    def purge_expired(self) -> int:
        """G33b: 만료된 캐시 엔트리 정리"""
        now = time.monotonic()
        expired = [k for k, (_, ts) in self._binding_cache.items() if (now - ts) >= self._CACHE_TTL]
        for k in expired:
            del self._binding_cache[k]
        return len(expired)


# 모듈 수준 인스턴스
binding_checker = SemanticBindingChecker()
