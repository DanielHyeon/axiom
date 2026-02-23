"""
Vision Analytics 서비스 (Phase V1 Full-spec).
실 DB(PostgreSQL) 연동: vision_analytics_* 테이블 + core_case 조회.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

# psycopg2 (Vision 이미 사용)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    for _path in ("/usr/lib/python3/dist-packages", os.path.expanduser("~/.local/lib/python3.12/site-packages")):
        if _path not in sys.path:
            sys.path.insert(0, _path)
    import psycopg2
    from psycopg2.extras import RealDictCursor


def _database_url() -> str:
    url = os.getenv("VISION_STATE_DATABASE_URL", "postgresql://arkos:arkos@localhost:5432/insolvency_os").strip()
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgres://")


class CaseNotFoundError(Exception):
    """케이스가 core_case 또는 vision_analytics_case_financial에 없음."""
    pass


class AnalyticsService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = (database_url or _database_url()).strip()
        self._postgres = _is_postgres(self.database_url)

    def _conn(self):
        if not self._postgres:
            raise RuntimeError("Analytics requires PostgreSQL")
        try:
            return psycopg2.connect(self.database_url)
        except psycopg2.OperationalError as e:
            raise RuntimeError("Analytics DB unavailable") from e

    def ensure_schema(self) -> None:
        """vision_analytics_* 테이블이 없으면 생성."""
        if not self._postgres:
            return
        sql_path = Path(__file__).resolve().parent.parent.parent / "migrations" / "001_vision_analytics.sql"
        if not sql_path.exists():
            return
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(open(sql_path).read())
            cur.close()
            conn.commit()

    def _row_to_kpi(self, r: dict[str, Any], period: str, period_label: str) -> dict[str, Any]:
        def num(v: Any) -> float | int:
            if v is None:
                return 0
            if isinstance(v, Decimal):
                return float(v)
            return v

        def pct(cur: float, prev: float | None) -> tuple[float, str]:
            if prev is None or prev == 0:
                return 0.0, "up"
            ch = ((cur - prev) / prev) * 100
            return round(ch, 1), "up" if ch >= 0 else "down"

        total = num(r.get("total_cases"))
        prev_total = r.get("prev_total_cases")
        active = num(r.get("active_cases"))
        prev_active = r.get("prev_active_cases")
        obligations = num(r.get("total_obligations_amount"))
        prev_obl = r.get("prev_total_obligations_amount")
        perf = num(r.get("avg_performance_rate"))
        prev_perf = r.get("prev_avg_performance_rate")
        duration = num(r.get("avg_case_duration_days"))
        prev_dur = r.get("prev_avg_case_duration_days")
        sat = num(r.get("stakeholder_satisfaction_rate"))
        prev_sat = r.get("prev_stakeholder_satisfaction_rate")

        ch_total, dir_total = pct(total, num(prev_total) if prev_total is not None else None)
        ch_active, dir_active = pct(active, num(prev_active) if prev_active is not None else None)
        ch_obl, dir_obl = pct(obligations, num(prev_obl) if prev_obl is not None else None)
        ch_perf, dir_perf = pct(perf, num(prev_perf) if prev_perf is not None else None)
        ch_dur, dir_dur = pct(duration, num(prev_dur) if prev_dur is not None else None)
        ch_sat, dir_sat = pct(sat, num(prev_sat) if prev_sat is not None else None)

        def fmt_obligations(v: float) -> str:
            if v >= 100000000:
                return f"{v/100000000:.0f}억원"
            return f"{v:,.0f}"

        return {
            "period": period,
            "period_label": period_label,
            "kpis": {
                "total_cases": {
                    "value": int(total),
                    "change_pct": ch_total,
                    "change_direction": dir_total,
                    "prev_period_value": int(prev_total) if prev_total is not None else None,
                },
                "active_cases": {
                    "value": int(active),
                    "change_pct": ch_active,
                    "change_direction": dir_active,
                    "prev_period_value": int(prev_active) if prev_active is not None else None,
                },
                "total_obligations_amount": {
                    "value": int(obligations),
                    "formatted": fmt_obligations(obligations),
                    "change_pct": ch_obl,
                    "change_direction": dir_obl,
                },
                "avg_performance_rate": {
                    "value": round(perf, 2),
                    "formatted": f"{perf*100:.1f}%",
                    "change_pct": ch_perf,
                    "change_direction": dir_perf,
                },
                "avg_case_duration_days": {
                    "value": int(duration),
                    "formatted": f"{int(duration)}일 (약 {max(1, int(duration/365))}년)",
                    "change_pct": ch_dur,
                    "change_direction": dir_dur,
                },
                "stakeholder_satisfaction_rate": {
                    "value": round(sat, 2),
                    "formatted": f"{sat*100:.1f}%",
                    "change_pct": ch_sat,
                    "change_direction": dir_sat,
                },
            },
            "computed_at": (r.get("computed_at") or datetime.utcnow()).isoformat().replace("+00:00", "Z") if hasattr(r.get("computed_at"), "isoformat") else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def get_summary(self, tenant_id: str, period: str, case_type: str | None) -> dict[str, Any]:
        self.ensure_schema()
        case_type = case_type or "ALL"
        with self._conn() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT * FROM vision_analytics_kpi
                WHERE tenant_id = %s AND period = %s AND case_type = %s
                """,
                (tenant_id, period, case_type),
            )
            row = cur.fetchone()
            if row:
                period_labels = {"YTD": "2026년 누적", "MTD": "이번 달", "QTD": "이번 분기", "LAST_YEAR": "전년", "ALL": "전체"}
                return self._row_to_kpi(dict(row), period, period_labels.get(period, period))
            # core_case에서 집계 (테이블 없으면 0으로)
            try:
                cur.execute(
                    """
                    SELECT
                        count(*) AS total_cases,
                        count(*) FILTER (WHERE status = 'IN_PROGRESS') AS active_cases
                    FROM core_case
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                agg = cur.fetchone()
            except psycopg2.ProgrammingError:
                agg = None
            cur.close()
        if agg:
            total = agg["total_cases"] or 0
            active = agg["active_cases"] or 0
        else:
            total = active = 0
        return self._row_to_kpi({
            "total_cases": total,
            "active_cases": active,
            "total_obligations_amount": 0,
            "avg_performance_rate": 0,
            "avg_case_duration_days": 0,
            "stakeholder_satisfaction_rate": 0,
            "prev_total_cases": None,
            "prev_active_cases": None,
            "prev_total_obligations_amount": None,
            "prev_avg_performance_rate": None,
            "prev_avg_case_duration_days": None,
            "prev_stakeholder_satisfaction_rate": None,
            "computed_at": datetime.utcnow(),
        }, period, {"YTD": "2026년 누적", "MTD": "이번 달", "QTD": "이번 분기", "LAST_YEAR": "전년", "ALL": "전체"}.get(period, period))

    def get_cases_trend(
        self,
        tenant_id: str,
        granularity: str,
        from_date: date,
        to_date: date,
        case_type: str | None,
        group_by: str | None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        with self._conn() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT period, new_cases, completed_cases, active_cases, total_obligations_registered
                FROM vision_analytics_trend
                WHERE tenant_id = %s AND granularity = %s
                  AND period >= %s AND period <= %s
                ORDER BY period
                """,
                (tenant_id, granularity, from_date.isoformat()[:7], to_date.isoformat()[:7]),
            )
            rows = cur.fetchall()
            if rows:
                series = [dict(r) for r in rows]
                cur.close()
                return {
                    "granularity": granularity,
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "series": series,
                    "case_type": case_type,
                    "group_by": group_by,
                }
            # core_case에서 월별 집계 (테이블 없으면 빈 시리즈)
            try:
                cur.execute(
                    """
                    SELECT
                        to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM') AS period,
                        count(*) AS new_cases,
                        count(*) FILTER (WHERE status = 'COMPLETED') AS completed_cases,
                        count(*) FILTER (WHERE status = 'IN_PROGRESS') AS active_cases
                    FROM core_case
                    WHERE tenant_id = %s AND created_at::date >= %s AND created_at::date <= %s
                    GROUP BY to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM')
                    ORDER BY 1
                    """,
                    (tenant_id, from_date, to_date),
                )
                db_rows = cur.fetchall()
            except psycopg2.ProgrammingError:
                db_rows = []
            cur.close()
        series = [
            {
                "period": r["period"],
                "new_cases": r["new_cases"] or 0,
                "completed_cases": r["completed_cases"] or 0,
                "active_cases": r["active_cases"] or 0,
                "total_obligations_registered": 0,
            }
            for r in db_rows
        ]
        return {
            "granularity": granularity,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "series": series,
            "case_type": case_type,
            "group_by": group_by,
        }

    def get_stakeholders_distribution(
        self,
        tenant_id: str,
        distribution_by: str,
        case_type: str | None,
        year: int | None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        with self._conn() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            q = """
                SELECT segment_label AS label, count, count_pct, amount, amount_pct, avg_satisfaction_rate
                FROM vision_analytics_stakeholder_dist
                WHERE tenant_id = %s AND distribution_by = %s
                """
            params = [tenant_id, distribution_by]
            if case_type:
                q += " AND (case_type = %s OR case_type IS NULL)"
                params.append(case_type)
            if year is not None:
                q += " AND (year = %s OR year IS NULL)"
                params.append(year)
            q += " ORDER BY count DESC"
            cur.execute(q, params)
            rows = cur.fetchall()
            cur.execute(
                "SELECT coalesce(sum(count),0) AS total_count, coalesce(sum(amount),0) AS total_amount FROM vision_analytics_stakeholder_dist WHERE tenant_id = %s AND distribution_by = %s",
                (tenant_id, distribution_by),
            )
            tot = cur.fetchone()
            cur.close()
        segments = [
            {
                "label": r["label"],
                "count": r["count"],
                "count_pct": float(r["count_pct"]) if r.get("count_pct") is not None else 0,
                "amount": r["amount"] or 0,
                "amount_pct": float(r["amount_pct"]) if r.get("amount_pct") is not None else 0,
                "avg_satisfaction_rate": float(r["avg_satisfaction_rate"]) if r.get("avg_satisfaction_rate") is not None else 0,
            }
            for r in rows
        ]
        return {
            "distribution_by": distribution_by,
            "total_count": int(tot["total_count"]) if tot else 0,
            "total_amount": int(tot["total_amount"]) if tot else 0,
            "segments": segments,
            "case_type": case_type,
            "year": year,
        }

    def get_performance_trend(
        self,
        tenant_id: str,
        granularity: str,
        stakeholder_type: str | None,
        case_type: str | None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        with self._conn() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            q = """
                SELECT period, avg_performance_rate, secured_rate, general_rate, priority_rate, case_count
                FROM vision_analytics_performance_trend
                WHERE tenant_id = %s AND granularity = %s
                """
            params = [tenant_id, granularity]
            if case_type:
                q += " AND (case_type = %s OR case_type IS NULL)"
                params.append(case_type)
            if stakeholder_type:
                q += " AND (stakeholder_type = %s OR stakeholder_type IS NULL)"
                params.append(stakeholder_type)
            q += " ORDER BY period"
            cur.execute(q, params)
            rows = cur.fetchall()
            cur.close()
        series = [
            {
                "period": r["period"],
                "avg_performance_rate": float(r["avg_performance_rate"]) if r.get("avg_performance_rate") is not None else 0,
                "secured_rate": float(r["secured_rate"]) if r.get("secured_rate") is not None else 0,
                "general_rate": float(r["general_rate"]) if r.get("general_rate") is not None else 0,
                "priority_rate": float(r["priority_rate"]) if r.get("priority_rate") is not None else 0,
                "case_count": r["case_count"] or 0,
            }
            for r in rows
        ]
        return {
            "granularity": granularity,
            "stakeholder_type": stakeholder_type,
            "case_type": case_type,
            "series": series,
        }

    def get_case_financial_summary(self, case_id: str, tenant_id: str) -> dict[str, Any]:
        self.ensure_schema()
        with self._conn() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    "SELECT id, title FROM core_case WHERE id = %s AND tenant_id = %s",
                    (case_id, tenant_id),
                )
                case_row = cur.fetchone()
            except psycopg2.ProgrammingError:
                case_row = None
            if not case_row:
                cur.close()
                raise CaseNotFoundError("사건을 찾을 수 없습니다")
            core_title = (case_row.get("title") or "") if case_row else ""
            cur.execute(
                "SELECT case_number, company_name, financials, execution_progress, stakeholder_breakdown FROM vision_analytics_case_financial WHERE case_id = %s",
                (case_id,),
            )
            fin = cur.fetchone()
            if not fin:
                # core_case에만 있는 경우 한 번 삽입 (실데이터 연동)
                cur.execute(
                    """
                    INSERT INTO vision_analytics_case_financial (case_id, tenant_id, case_number, company_name, financials, execution_progress, stakeholder_breakdown)
                    VALUES (%s, %s, %s, %s, '{}', '{}', '[]')
                    ON CONFLICT (case_id) DO UPDATE SET company_name = EXCLUDED.company_name, updated_at = NOW()
                    """,
                    (case_id, tenant_id, case_id, core_title),
                )
                conn.commit()
            cur.close()
        if fin:
            financials = fin["financials"] if isinstance(fin["financials"], dict) else (json.loads(fin["financials"]) if fin["financials"] else {})
            execution_progress = fin["execution_progress"] if isinstance(fin["execution_progress"], dict) else (json.loads(fin["execution_progress"]) if fin["execution_progress"] else {})
            stakeholder_breakdown = fin["stakeholder_breakdown"] if isinstance(fin["stakeholder_breakdown"], list) else (json.loads(fin["stakeholder_breakdown"]) if fin["stakeholder_breakdown"] else [])
            return {
                "case_id": case_id,
                "case_number": fin["case_number"] or case_id,
                "company_name": fin["company_name"] or core_title,
                "financials": financials,
                "execution_progress": execution_progress,
                "stakeholder_breakdown": stakeholder_breakdown,
            }
        default_financials = {
            "total_assets": 0,
            "total_liabilities": 0,
            "total_obligations": 0,
            "verified_obligations": 0,
            "pending_obligations": 0,
            "debt_ratio": 0.0,
            "latest_ebitda": 0,
            "cash_balance": 0,
        }
        default_progress = {
            "plan_total": 0,
            "paid_to_date": 0,
            "progress_pct": 0.0,
            "next_payment_date": None,
            "next_payment_amount": 0,
        }
        return {
            "case_id": case_id,
            "case_number": case_id,
            "company_name": core_title,
            "financials": default_financials,
            "execution_progress": default_progress,
            "stakeholder_breakdown": [],
        }

    def get_dashboards(self, tenant_id: str) -> dict[str, Any]:
        self.ensure_schema()
        with self._conn() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT id, title, widgets_json FROM vision_analytics_dashboards WHERE tenant_id = %s ORDER BY id",
                (tenant_id,),
            )
            rows = cur.fetchall()
            cur.close()
        if rows:
            dashboards = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "widgets": r["widgets_json"] if isinstance(r["widgets_json"], list) else (json.loads(r["widgets_json"]) if r["widgets_json"] else []),
                }
                for r in rows
            ]
            return {"dashboards": dashboards}
        return {
            "dashboards": [
                {
                    "id": "case-overview",
                    "title": "사건 개요 대시보드",
                    "widgets": [
                        {"id": "kpi-summary", "type": "summary", "source": "/api/v3/analytics/summary"},
                        {"id": "case-trend", "type": "timeseries", "source": "/api/v3/analytics/cases/trend"},
                    ],
                },
                {
                    "id": "stakeholder-performance",
                    "title": "이해관계자 성과 대시보드",
                    "widgets": [
                        {"id": "stakeholder-distribution", "type": "distribution", "source": "/api/v3/analytics/stakeholders/distribution"},
                        {"id": "performance-trend", "type": "timeseries", "source": "/api/v3/analytics/performance/trend"},
                    ],
                },
            ]
        }


_analytics_service: AnalyticsService | None = None


def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
