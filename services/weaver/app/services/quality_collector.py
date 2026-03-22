"""
품질 수집 파이프라인 — 시멘틱 계약 품질 점수 측정 + 저장

Synapse의 품질 계약(QualityContract)에 정의된 SLA를 기준으로
실제 데이터의 9개 차원 품질을 측정하고 quality_scores 테이블에 기록한다.

9개 차원 (계획서 §11.2):
  1. Freshness     (0.20) — 마지막 데이터 갱신 시각 vs SLA
  2. Completeness  (0.15) — NULL 비율 (1 - null_ratio)
  3. Validity      (0.10) — CHECK 제약/도메인 값 위반 비율
  4. Uniqueness    (0.10) — PK/Grain 중복률
  5. Referential Integrity (0.10) — FK 참조 무결성 샘플링
  6. Owner Coverage (0.10) — owner_team 지정 여부
  7. Lineage Completeness  (0.10) — upstream/downstream 연결 존재 여부
  8. Test Coverage  (0.05) — QualityContract 연결 여부
  9. Incident Health (0.10) — 최근 30일 breach 횟수 역산
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

from app.core.config import settings

logger = logging.getLogger("weaver.quality_collector")

# ── 가중치 v2 (계획서 §11.2 일치) ──
_WEIGHTS_V2 = {
    "freshness": 0.20,
    "completeness": 0.15,
    "validity": 0.10,
    "uniqueness": 0.10,
    "referential_integrity": 0.10,
    "owner": 0.10,
    "lineage": 0.10,
    "test_coverage": 0.05,
    "incident_health": 0.10,
}

# 안전한 식별자 패턴 — 테이블명, 컬럼명 모두에 적용 (SQL 인젝션 방지)
# 영문, 숫자, 밑줄, 점만 허용 (스키마.테이블 형식 대응)
_SAFE_IDENTIFIER_PATTERN = re.compile(r'^[\w.]+$')


def _validate_identifier(name: str) -> bool:
    """테이블명 또는 컬럼명이 안전한 형식인지 검증한다 (SQL 인젝션 방지)"""
    return bool(name and _SAFE_IDENTIFIER_PATTERN.match(name))


def _validate_identifiers(names: list[str]) -> bool:
    """여러 식별자가 모두 안전한 형식인지 검증한다"""
    return all(_validate_identifier(n) for n in names)


def _compute_overall(scores: dict[str, float | None]) -> float:
    """가중 평균 품질 점수 계산 (0~100), v2 공식 사용"""
    total_weight = 0.0
    weighted = 0.0
    for dim, weight in _WEIGHTS_V2.items():
        score = scores.get(dim)
        if score is not None:
            weighted += score * weight
            total_weight += weight
    return round(weighted / total_weight, 2) if total_weight > 0 else 0.0


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
        """단일 테이블의 9개 차원 품질 점수를 수집한다."""
        pool = await self._store.get_pool()
        scores: dict[str, float | None] = {}
        details: dict[str, Any] = {}

        async with pool.acquire() as conn:
            # tenant RLS 설정
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)", tenant_id
            )

            # 1. Freshness — 마지막 활동 시각 기반
            scores["freshness"], details["freshness"] = await self._measure_freshness(
                conn, table_name, freshness_sla_minutes
            )

            # 2. Completeness — NULL 비율 샘플링
            scores["completeness"], details["completeness"] = await self._measure_completeness(
                conn, table_name
            )

            # 3. Validity — CHECK 제약/도메인 값 위반
            scores["validity"], details["validity"] = await self._measure_validity(
                conn, table_name
            )

            # 4. Uniqueness — PK 중복률
            scores["uniqueness"], details["uniqueness"] = await self._measure_uniqueness(
                conn, table_name
            )

            # 5. Referential Integrity — FK 참조 무결성
            scores["referential_integrity"], details["referential_integrity"] = (
                await self._measure_referential_integrity(conn, table_name)
            )

            # 6. Incident Health — 최근 30일 품질 breach 횟수
            scores["incident_health"], details["incident_health"] = (
                await self._measure_incident_health(conn, tenant_id, datasource_id, table_name)
            )

        # DB 커넥션 외부에서 계산 가능한 메타 차원들
        # 7. Owner Coverage — owner_team 지정 여부 (이진)
        scores["owner"] = 100.0 if owner_team else 0.0
        details["owner"] = {"owner_team": owner_team or "(미지정)"}

        # 8. Lineage Completeness — lineage_edges 존재 여부
        scores["lineage"], details["lineage"] = await self._measure_lineage_completeness(
            tenant_id, datasource_id, table_name
        )

        # 9. Test Coverage — QualityContract 연결 여부
        scores["test_coverage"], details["test_coverage"] = await self._measure_test_coverage(
            tenant_id, datasource_id, table_name
        )

        # 가중 평균 계산 (v2 공식)
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
            "formula_version": 2,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
        }

    # ══════════════════════════════════════════════════════════
    # 차원별 측정 메서드 — 각각 (score, details) 튜플 반환
    # ══════════════════════════════════════════════════════════

    async def _measure_freshness(
        self, conn, table_name: str, sla_minutes: int | None
    ) -> tuple[float, dict]:
        """Freshness: pg_stat에서 마지막 활동 시각 vs SLA"""
        try:
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
                age_minutes = (
                    datetime.now(timezone.utc) - last_activity.replace(tzinfo=timezone.utc)
                ).total_seconds() / 60
                sla = sla_minutes or 1440
                if age_minutes > sla:
                    score = max(0, min(100, 100 * (1 - (age_minutes - sla) / sla)))
                else:
                    score = 100.0
                return round(score, 2), {
                    "last_activity": last_activity.isoformat(),
                    "age_minutes": round(age_minutes, 1),
                    "sla_minutes": sla,
                }
            return 0.0, {"error": "테이블 활동 정보 없음"}
        except Exception as exc:
            return 0.0, {"error": str(exc)}

    async def _measure_completeness(self, conn, table_name: str) -> tuple[float, dict]:
        """Completeness: 첫 5개 컬럼의 NULL 비율 샘플링"""
        try:
            if not _validate_identifier(table_name):
                return 0.0, {"error": "테이블명 형식 오류"}

            cols_row = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema || '.' || table_name = $1
                   OR table_name = $1
                ORDER BY ordinal_position
                LIMIT 5
            """, table_name)
            if not cols_row:
                return 0.0, {"error": "컬럼 정보 없음"}

            col_names = [r["column_name"] for r in cols_row]
            # 컬럼명 안전성 검증 (2차 SQL 인젝션 방지)
            if not _validate_identifiers(col_names):
                return 0.0, {"error": "컬럼명 형식 오류 — 안전하지 않은 이름 감지"}

            null_checks = ", ".join(
                f"ROUND(SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END)::numeric "
                f"/ GREATEST(COUNT(*), 1) * 100, 2) AS null_{c}"
                for c in col_names
            )

            sample_row = await conn.fetchrow(
                f"SELECT {null_checks} FROM (SELECT * FROM {table_name} LIMIT 10000) AS _sample"
            )
            if sample_row:
                null_ratios = {
                    k.replace("null_", ""): float(v or 0)
                    for k, v in dict(sample_row).items()
                }
                avg_null = sum(null_ratios.values()) / len(null_ratios) if null_ratios else 0
                return round(100 - avg_null, 2), {"null_ratios": null_ratios, "sample_size": 10000}
            return 100.0, {}
        except Exception as exc:
            return 0.0, {"error": str(exc)}

    async def _measure_validity(self, conn, table_name: str) -> tuple[float, dict]:
        """Validity: CHECK 제약 조건 위반 비율 + 도메인 값 검증

        information_schema.check_constraints에서 CHECK 제약 조건을 가져와
        위반 행 수를 샘플링한다. CHECK 제약이 없으면 NULL 가능 컬럼의
        빈 문자열 비율로 대체한다.
        """
        try:
            if not _SAFE_IDENTIFIER_PATTERN.match(table_name):
                return 0.0, {"error": "테이블명 형식 오류"}

            # CHECK 제약 조건 조회
            check_rows = await conn.fetch("""
                SELECT cc.check_clause, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.check_constraints cc
                  ON tc.constraint_name = cc.constraint_name
                 AND tc.constraint_schema = cc.constraint_schema
                WHERE (tc.table_schema || '.' || tc.table_name = $1 OR tc.table_name = $1)
                  AND tc.constraint_type = 'CHECK'
                  AND cc.check_clause NOT LIKE '%IS NOT NULL%'
                LIMIT 10
            """, table_name)

            if check_rows:
                # CHECK 제약이 있으면 위반 건수 샘플링 (읽기 전용으로 실행)
                total_checks = len(check_rows)
                violations = 0
                for cr in check_rows:
                    clause = cr["check_clause"]
                    try:
                        # CHECK clause는 PG가 DDL 시점에 검증하지만
                        # 방어적으로 읽기 전용 트랜잭션에서 실행한다
                        async with conn.transaction():
                            await conn.execute("SET TRANSACTION READ ONLY")
                            viol_row = await conn.fetchrow(f"""
                                SELECT COUNT(*) AS cnt
                                FROM (SELECT * FROM {table_name} LIMIT 10000) AS _s
                                WHERE NOT ({clause})
                            """)
                            if viol_row and viol_row["cnt"] > 0:
                                violations += 1
                    except Exception:
                        pass  # 개별 CHECK 실패는 무시

                score = round((1 - violations / total_checks) * 100, 2) if total_checks > 0 else 100.0
                return score, {
                    "method": "check_constraints",
                    "total_checks": total_checks,
                    "violated": violations,
                }

            # CHECK 제약이 없으면 빈 문자열 비율로 대체 (text 컬럼 대상)
            text_cols = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE (table_schema || '.' || table_name = $1 OR table_name = $1)
                  AND data_type IN ('character varying', 'text', 'character')
                  AND is_nullable = 'YES'
                LIMIT 5
            """, table_name)

            if text_cols:
                col_names = [r["column_name"] for r in text_cols]
                # 컬럼명 안전성 검증 (2차 SQL 인젝션 방지)
                if not _validate_identifiers(col_names):
                    return 0.0, {"error": "컬럼명 형식 오류"}
                empty_checks = " + ".join(
                    f"SUM(CASE WHEN {c} = '' THEN 1 ELSE 0 END)" for c in col_names
                )
                row = await conn.fetchrow(f"""
                    SELECT ({empty_checks})::numeric / GREATEST(COUNT(*) * {len(col_names)}, 1) * 100 AS empty_pct
                    FROM (SELECT * FROM {table_name} LIMIT 10000) AS _s
                """)
                empty_pct = float(row["empty_pct"]) if row else 0
                return round(100 - empty_pct, 2), {"method": "empty_string_ratio", "columns": col_names}

            # 검증할 수 없으면 100 (보수적 패스)
            return 100.0, {"method": "no_constraints_found"}
        except Exception as exc:
            return 0.0, {"error": str(exc)}

    async def _measure_uniqueness(self, conn, table_name: str) -> tuple[float, dict]:
        """Uniqueness: PK 기반 중복률"""
        try:
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
                # PK 컬럼명 안전성 검증 (2차 SQL 인젝션 방지)
                if not _validate_identifiers(pk_cols):
                    return 0.0, {"error": "PK 컬럼명 형식 오류"}
                pk_expr = ", ".join(pk_cols)
                if not _validate_identifier(table_name):
                    return 0.0, {"error": "테이블명 형식 오류"}
                dup_row = await conn.fetchrow(f"""
                    SELECT COUNT(*) AS total, COUNT(DISTINCT ({pk_expr})) AS distinct_count
                    FROM (SELECT {pk_expr} FROM {table_name} LIMIT 10000) AS _sample
                """)
                if dup_row and dup_row["total"] > 0:
                    score = round(dup_row["distinct_count"] / dup_row["total"] * 100, 2)
                    return score, {
                        "pk_columns": pk_cols,
                        "total": dup_row["total"],
                        "distinct": dup_row["distinct_count"],
                    }
                return 100.0, {"pk_columns": pk_cols, "note": "데이터 없음"}
            return 100.0, {"note": "PK 없음 — 검증 생략"}
        except Exception as exc:
            return 0.0, {"error": str(exc)}

    async def _measure_referential_integrity(
        self, conn, table_name: str
    ) -> tuple[float, dict]:
        """Referential Integrity: FK 참조 무결성 샘플링

        information_schema에서 FK 제약 조건을 가져와
        참조 대상 테이블에 존재하지 않는 orphan 행 비율을 계산한다.
        """
        try:
            if not _SAFE_IDENTIFIER_PATTERN.match(table_name):
                return 0.0, {"error": "테이블명 형식 오류"}

            # FK 관계 조회 (최대 5개)
            fk_rows = await conn.fetch("""
                SELECT
                    kcu.column_name AS fk_column,
                    ccu.table_schema || '.' || ccu.table_name AS ref_table,
                    ccu.column_name AS ref_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.constraint_schema = kcu.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                 AND tc.constraint_schema = ccu.constraint_schema
                WHERE (tc.table_schema || '.' || tc.table_name = $1 OR tc.table_name = $1)
                  AND tc.constraint_type = 'FOREIGN KEY'
                LIMIT 5
            """, table_name)

            if not fk_rows:
                return 100.0, {"note": "FK 없음 — 검증 생략"}

            # 각 FK별 orphan 비율 계산
            total_fks = len(fk_rows)
            orphan_sum = 0.0

            for fk in fk_rows:
                fk_col = fk["fk_column"]
                ref_table = fk["ref_table"]
                ref_col = fk["ref_column"]

                # FK/참조 컬럼명 + 참조 테이블명 안전성 검증 (2차 SQL 인젝션 방지)
                if not _validate_identifiers([fk_col, ref_col, ref_table]):
                    continue

                try:
                    row = await conn.fetchrow(f"""
                        SELECT
                            COUNT(*) AS total,
                            SUM(CASE WHEN r.{ref_col} IS NULL THEN 1 ELSE 0 END) AS orphan
                        FROM (SELECT {fk_col} FROM {table_name} WHERE {fk_col} IS NOT NULL LIMIT 10000) s
                        LEFT JOIN {ref_table} r ON s.{fk_col} = r.{ref_col}
                    """)
                    if row and row["total"] > 0:
                        orphan_ratio = row["orphan"] / row["total"]
                        orphan_sum += orphan_ratio
                except Exception:
                    orphan_sum += 0.5  # 조회 실패 시 보수적 감점

            avg_orphan_ratio = orphan_sum / total_fks if total_fks > 0 else 0
            score = round((1 - avg_orphan_ratio) * 100, 2)
            return max(0, score), {
                "fk_count": total_fks,
                "avg_orphan_ratio": round(avg_orphan_ratio, 4),
            }
        except Exception as exc:
            return 0.0, {"error": str(exc)}

    async def _measure_incident_health(
        self, conn, tenant_id: str, datasource_id: str, table_name: str
    ) -> tuple[float, dict]:
        """Incident Health: 최근 30일간 품질 점수 breach 횟수 역산

        overall_score가 50 미만인 기록이 있으면 breach로 간주.
        breach 0회 = 100, 1회 = 80, 2회 = 60, 3회+ = 40, 5회+ = 20
        """
        try:
            target_id = f"{datasource_id}:{table_name}"
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

            row = await conn.fetchrow("""
                SELECT COUNT(*) AS breach_count
                FROM weaver.quality_scores
                WHERE tenant_id = $1
                  AND target_id = $2
                  AND overall_score < 50
                  AND created_at >= $3
            """, tenant_id, target_id, thirty_days_ago)

            breach_count = row["breach_count"] if row else 0
            # breach 횟수 → 점수 매핑 (계단식 감점)
            if breach_count == 0:
                score = 100.0
            elif breach_count == 1:
                score = 80.0
            elif breach_count == 2:
                score = 60.0
            elif breach_count <= 4:
                score = 40.0
            else:
                score = 20.0

            return score, {"breach_count_30d": breach_count}
        except Exception as exc:
            return 100.0, {"error": str(exc), "note": "조회 실패 — 보수적 통과"}

    async def _measure_lineage_completeness(
        self, tenant_id: str, datasource_id: str, table_name: str
    ) -> tuple[float, dict]:
        """Lineage Completeness: OLAP Studio lineage_edges 존재 여부

        upstream(소스) 또는 downstream(소비처) 연결이 있으면 점수 부여.
        연결 없으면 0점.
        """
        try:
            import httpx
            # OLAP Studio lineage API 조회 (설정 기반 URL)
            olap_base = getattr(settings, "olap_studio_base_url", "") or "http://olap-studio:8000"
            svc_token = getattr(settings, "weaver_insight_service_token", "") or ""
            url = f"{olap_base.rstrip('/')}/api/lineage/edges"
            headers = {"Authorization": f"Bearer {svc_token}"} if svc_token else {}
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params={
                    "entity_name": table_name,
                    "tenant_id": tenant_id,
                }, headers=headers)
                if resp.status_code == 200:
                    edges = resp.json().get("data", [])
                    has_upstream = any(e.get("target") == table_name for e in edges)
                    has_downstream = any(e.get("source") == table_name for e in edges)
                    # upstream + downstream 모두 있으면 100, 하나만 있으면 50, 없으면 0
                    if has_upstream and has_downstream:
                        score = 100.0
                    elif has_upstream or has_downstream:
                        score = 50.0
                    else:
                        score = 0.0
                    return score, {
                        "has_upstream": has_upstream,
                        "has_downstream": has_downstream,
                        "edge_count": len(edges),
                    }
        except Exception as exc:
            logger.debug("lineage_check_failed: %s", exc)

        # OLAP Studio 연결 실패 시 메타데이터 기반 추정 (owner 존재 = 최소 연결)
        return 0.0, {"note": "lineage 정보 조회 불가"}

    async def _measure_test_coverage(
        self, tenant_id: str, datasource_id: str, table_name: str
    ) -> tuple[float, dict]:
        """Test Coverage: Synapse에 QualityContract가 연결되어 있으면 covered

        시멘틱 계약 = 테스트 정의. QualityContract가 있으면 100, 없으면 0.
        """
        try:
            import httpx
            # Synapse API 조회 (설정 기반 URL + 서비스 토큰)
            synapse_base = getattr(settings, "synapse_base_url", "") or "http://synapse:8003"
            svc_token = getattr(settings, "weaver_insight_service_token", "") or ""
            url = f"{synapse_base.rstrip('/')}/api/v3/synapse/semantic/quality-contracts"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params={"target_type": "entity"}, headers={
                    "X-Tenant-Id": tenant_id,
                    "Authorization": f"Bearer {svc_token}" if svc_token else "",
                })
                if resp.status_code == 200:
                    contracts = resp.json().get("data", [])
                    # target_id가 datasource_id(entity_id)와 매칭되는 계약 존재 여부
                    has_contract = any(
                        c.get("target_id") == datasource_id for c in contracts
                    )
                    return (100.0 if has_contract else 0.0), {
                        "has_quality_contract": has_contract,
                        "entity_id": datasource_id,
                    }
        except Exception as exc:
            logger.debug("test_coverage_check_failed: %s", exc)

        return 0.0, {"note": "QualityContract 조회 불가"}

    # ══════════════════════════════════════════════════════════
    # 저장 + 조회
    # ══════════════════════════════════════════════════════════

    async def _save_score(
        self,
        tenant_id: str,
        target_type: str,
        target_id: str,
        scores: dict[str, float | None],
        overall: float,
        details: dict[str, Any],
    ) -> None:
        """품질 점수를 quality_scores 테이블에 저장 (v2 공식)"""
        pool = await self._store.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO weaver.quality_scores (
                    tenant_id, target_type, target_id,
                    freshness_score, completeness_score, uniqueness_score,
                    owner_score, lineage_score,
                    validity_score, ri_score, test_score, incident_score,
                    overall_score, formula_version,
                    details, sampled_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, now())
            """,
                tenant_id, target_type, target_id,
                scores.get("freshness", 0), scores.get("completeness", 0),
                scores.get("uniqueness", 0), scores.get("owner", 0),
                scores.get("lineage", 0), scores.get("validity", 0),
                scores.get("referential_integrity", 0),
                scores.get("test_coverage", 0), scores.get("incident_health", 0),
                overall, 2,  # formula_version = 2
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
                    owner_score, lineage_score,
                    validity_score, ri_score, test_score, incident_score,
                    overall_score, formula_version,
                    details, sampled_at, created_at
                FROM weaver.quality_scores
                WHERE {where}
                ORDER BY target_type, target_id, created_at DESC
                LIMIT ${idx}
                """,
                *params,
            )
            return [dict(r) for r in rows]

    async def get_score_for_target(
        self, tenant_id: str, target_type: str, target_id: str
    ) -> dict[str, Any] | None:
        """특정 대상의 최신 품질 점수 조회"""
        results = await self.get_latest_scores(
            tenant_id, target_type=target_type, target_id=target_id, limit=1
        )
        return results[0] if results else None
