"""
품질 수집 파이프라인 — 시멘틱 계약 품질 점수 측정 + 저장

Synapse의 품질 계약(QualityContract)에 정의된 SLA를 기준으로
실제 데이터의 freshness, completeness, uniqueness를 측정하고
quality_scores 테이블에 기록한다.

9개 차원 중 자동 수집 가능한 3개를 우선 구현:
- Freshness: 마지막 데이터 갱신 시각 vs SLA
- Completeness: NULL 비율 (1 - null_ratio)
- Uniqueness: PK/Grain 중복률
나머지 6개 (validity, referential_integrity, owner_coverage,
lineage_completeness, test_coverage, incident_health)는
각각 수동 입력 또는 후속 자동화 대상.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger("weaver.quality_collector")

# 가중치 (문서 §11.2 공식 기반)
_WEIGHTS = {
    "freshness": 0.25,
    "completeness": 0.25,
    "uniqueness": 0.20,
    "owner": 0.10,
    "lineage": 0.10,
    # validity, test_coverage, incident_health는 후속 추가
}


def _compute_overall(scores: dict[str, float]) -> float:
    """가중 평균 품질 점수 계산 (0~100)"""
    total_weight = sum(_WEIGHTS.get(k, 0) for k in scores if scores[k] is not None)
    if total_weight == 0:
        return 0.0
    weighted = sum(scores.get(k, 0) * _WEIGHTS.get(k, 0) for k in scores if scores[k] is not None)
    return round(weighted / total_weight, 2)


class QualityCollector:
    """시멘틱 계약 대상의 데이터 품질을 수집하고 점수를 저장한다."""

    def __init__(self, insight_store):
        self._store = insight_store

    async def collect_table_quality(
        self,
        tenant_id: str,
        datasource_id: str,
        table_name: str,
        freshness_sla_minutes: int | None = None,
        owner_team: str | None = None,
    ) -> dict[str, Any]:
        """단일 테이블의 품질 점수를 수집한다.

        실제 DB에 쿼리를 실행하여 freshness, completeness, uniqueness를 측정.
        """
        pool = await self._store.get_pool()
        scores: dict[str, float] = {}
        details: dict[str, Any] = {}

        async with pool.acquire() as conn:
            # tenant RLS 설정
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", tenant_id)

            # ── Freshness: information_schema에서 테이블 최종 변경 추정 ──
            try:
                # pg_stat_user_tables에서 마지막 분석/변경 시각 추정
                row = await conn.fetchrow("""
                    SELECT
                        GREATEST(last_autovacuum, last_autoanalyze, last_vacuum, last_analyze) AS last_activity,
                        n_live_tup AS row_count
                    FROM pg_stat_user_tables
                    WHERE schemaname || '.' || relname = $1
                       OR relname = $1
                    LIMIT 1
                """, table_name)
                if row and row["last_activity"]:
                    last_activity = row["last_activity"]
                    age_minutes = (datetime.now(timezone.utc) - last_activity.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    sla = freshness_sla_minutes or 1440  # 기본 24시간
                    # SLA 내면 100, 초과 시 비례 감소 (최소 0)
                    freshness = max(0, min(100, 100 * (1 - (age_minutes - sla) / sla))) if age_minutes > sla else 100.0
                    scores["freshness"] = round(freshness, 2)
                    details["freshness"] = {
                        "last_activity": last_activity.isoformat(),
                        "age_minutes": round(age_minutes, 1),
                        "sla_minutes": sla,
                    }
                else:
                    scores["freshness"] = 0.0
                    details["freshness"] = {"error": "테이블 활동 정보 없음"}
            except Exception as exc:
                scores["freshness"] = 0.0
                details["freshness"] = {"error": str(exc)}

            # ── Completeness: NULL 비율 샘플링 ──
            try:
                # 첫 5개 컬럼의 NULL 비율을 샘플링 (전체 스캔 방지 — TABLESAMPLE)
                cols_row = await conn.fetch("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema || '.' || table_name = $1
                       OR table_name = $1
                    ORDER BY ordinal_position
                    LIMIT 5
                """, table_name)
                if cols_row:
                    col_names = [r["column_name"] for r in cols_row]
                    # 각 컬럼별 NULL 비율 계산 (최대 10000행 샘플)
                    null_checks = ", ".join(
                        f"ROUND(SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END)::numeric / GREATEST(COUNT(*), 1) * 100, 2) AS null_{c}"
                        for c in col_names
                    )
                    # 안전한 테이블명 검증 (영문, 숫자, _, . 만 허용)
                    import re
                    if re.match(r'^[\w.]+$', table_name):
                        sample_row = await conn.fetchrow(
                            f"SELECT {null_checks} FROM (SELECT * FROM {table_name} LIMIT 10000) AS _sample"
                        )
                        if sample_row:
                            null_ratios = {k.replace("null_", ""): float(v or 0) for k, v in dict(sample_row).items()}
                            avg_null = sum(null_ratios.values()) / len(null_ratios) if null_ratios else 0
                            completeness = round(100 - avg_null, 2)
                            scores["completeness"] = completeness
                            details["completeness"] = {"null_ratios": null_ratios, "sample_size": 10000}
                        else:
                            scores["completeness"] = 100.0
                    else:
                        scores["completeness"] = 0.0
                        details["completeness"] = {"error": "테이블명 형식 오류"}
                else:
                    scores["completeness"] = 0.0
                    details["completeness"] = {"error": "컬럼 정보 없음"}
            except Exception as exc:
                scores["completeness"] = 0.0
                details["completeness"] = {"error": str(exc)}

            # ── Uniqueness: 행 중복률 (PK 기반) ──
            try:
                # PK 컬럼 확인
                pk_row = await conn.fetch("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    JOIN pg_class c ON c.oid = i.indrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE i.indisprimary
                      AND (n.nspname || '.' || c.relname = $1 OR c.relname = $1)
                """, table_name)
                if pk_row:
                    pk_cols = [r["attname"] for r in pk_row]
                    pk_expr = ", ".join(pk_cols)
                    if re.match(r'^[\w.]+$', table_name):
                        dup_row = await conn.fetchrow(f"""
                            SELECT COUNT(*) AS total, COUNT(DISTINCT ({pk_expr})) AS distinct_count
                            FROM (SELECT {pk_expr} FROM {table_name} LIMIT 10000) AS _sample
                        """)
                        if dup_row and dup_row["total"] > 0:
                            uniqueness = round(dup_row["distinct_count"] / dup_row["total"] * 100, 2)
                            scores["uniqueness"] = uniqueness
                            details["uniqueness"] = {
                                "pk_columns": pk_cols,
                                "total": dup_row["total"],
                                "distinct": dup_row["distinct_count"],
                            }
                        else:
                            scores["uniqueness"] = 100.0
                    else:
                        scores["uniqueness"] = 0.0
                else:
                    # PK 없으면 100으로 간주 (검증 불가)
                    scores["uniqueness"] = 100.0
                    details["uniqueness"] = {"note": "PK 없음 — 검증 생략"}
            except Exception as exc:
                scores["uniqueness"] = 0.0
                details["uniqueness"] = {"error": str(exc)}

        # Owner/Lineage는 메타데이터 기반 (0 or 100)
        scores["owner"] = 100.0 if owner_team else 0.0
        scores["lineage"] = 0.0  # 후속 구현 (리니지 추적 여부)

        overall = _compute_overall(scores)

        # DB에 저장
        await self._save_score(
            tenant_id=tenant_id,
            target_type="table",
            target_id=f"{datasource_id}:{table_name}",
            scores=scores,
            overall=overall,
            details=details,
        )

        return {
            "target_type": "table",
            "target_id": f"{datasource_id}:{table_name}",
            "scores": scores,
            "overall_score": overall,
            "details": details,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _save_score(
        self,
        tenant_id: str,
        target_type: str,
        target_id: str,
        scores: dict[str, float],
        overall: float,
        details: dict[str, Any],
    ) -> None:
        """품질 점수를 quality_scores 테이블에 저장"""
        pool = await self._store.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO weaver.quality_scores (
                    tenant_id, target_type, target_id,
                    freshness_score, completeness_score, uniqueness_score,
                    owner_score, lineage_score, overall_score,
                    details, sampled_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now())
            """,
                tenant_id, target_type, target_id,
                scores.get("freshness", 0), scores.get("completeness", 0), scores.get("uniqueness", 0),
                scores.get("owner", 0), scores.get("lineage", 0), overall,
                json.dumps(details, ensure_ascii=False),
            )

    async def get_latest_scores(
        self,
        tenant_id: str,
        target_type: str | None = None,
        target_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """최신 품질 점수 조회"""
        pool = await self._store.get_pool()
        async with pool.acquire() as conn:
            conditions = ["tenant_id = $1"]
            params: list[Any] = [tenant_id]
            idx = 2
            if target_type:
                conditions.append(f"target_type = ${idx}")
                params.append(target_type)
                idx += 1
            if target_id:
                conditions.append(f"target_id = ${idx}")
                params.append(target_id)
                idx += 1
            where = " AND ".join(conditions)
            params.append(limit)
            rows = await conn.fetch(
                f"""
                SELECT DISTINCT ON (target_type, target_id)
                    id, tenant_id, target_type, target_id,
                    freshness_score, completeness_score, uniqueness_score,
                    owner_score, lineage_score, overall_score,
                    details, sampled_at, created_at
                FROM weaver.quality_scores
                WHERE {where}
                ORDER BY target_type, target_id, created_at DESC
                LIMIT ${idx}
                """,
                *params,
            )
            return [dict(r) for r in rows]

    async def get_score_for_target(self, tenant_id: str, target_type: str, target_id: str) -> dict[str, Any] | None:
        """특정 대상의 최신 품질 점수 조회"""
        results = await self.get_latest_scores(tenant_id, target_type=target_type, target_id=target_id, limit=1)
        return results[0] if results else None
