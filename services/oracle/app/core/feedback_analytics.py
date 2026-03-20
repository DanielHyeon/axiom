"""피드백 통계 집계 모듈.

query_history + query_feedback 테이블을 조인하여
피드백 통계를 집계하는 SQL 쿼리를 제공한다.

테이블 스키마:
- oracle.query_history: id, tenant_id, user_id, question, sql, status,
  execution_time_ms, datasource_id, tables_used, created_at
- oracle.query_feedback: id, query_id, tenant_id, user_id, rating,
  corrected_sql, comment, created_at
"""

from typing import Any
from uuid import UUID

import structlog

from app.core.config import settings

logger = structlog.get_logger()


class FeedbackAnalytics:
    """피드백 통계 집계 — asyncpg 기반 직접 쿼리."""

    def __init__(self, database_url: str | None = None):
        self._database_url = database_url or settings.QUERY_HISTORY_DATABASE_URL

    async def _fetch_all(self, sql: str, params: list) -> list[dict]:
        """비동기 쿼리 실행 후 결과를 딕셔너리 리스트로 반환한다."""
        import asyncpg
        # asyncpg은 postgresql+asyncpg:// 형식을 지원하지 않으므로 변환
        dsn = self._database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(sql, *params)
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def _fetch_one(self, sql: str, params: list) -> dict | None:
        """단일 행 조회."""
        rows = await self._fetch_all(sql, params)
        return rows[0] if rows else None

    async def get_summary(
        self, tenant_id: str, date_from: str, date_to: str
    ) -> dict[str, Any]:
        """요약 통계: 총 쿼리, 피드백 수, positive/negative/partial 비율, 평균 응답시간."""
        sql = """
        WITH qh AS (
            SELECT id, execution_time_ms
            FROM query_history
            WHERE tenant_id = $1
              AND created_at >= $2::date
              AND created_at < ($3::date + INTERVAL '1 day')
        ),
        fb AS (
            SELECT rating
            FROM query_feedback
            WHERE tenant_id = $1
              AND created_at >= $2::date
              AND created_at < ($3::date + INTERVAL '1 day')
        )
        SELECT
            (SELECT COUNT(*) FROM qh) AS total_queries,
            (SELECT COUNT(*) FROM fb) AS total_feedbacks,
            (SELECT COUNT(*) FILTER (WHERE rating = 'positive') FROM fb) AS positive_count,
            (SELECT COUNT(*) FILTER (WHERE rating = 'negative') FROM fb) AS negative_count,
            (SELECT COUNT(*) FILTER (WHERE rating = 'partial') FROM fb) AS partial_count,
            (SELECT COALESCE(AVG(execution_time_ms), 0) FROM qh) AS avg_execution_time_ms
        """
        row = await self._fetch_one(sql, [tenant_id, date_from, date_to])
        if not row:
            return {
                "total_queries": 0,
                "total_feedbacks": 0,
                "positive_rate": 0,
                "negative_rate": 0,
                "partial_rate": 0,
                "avg_execution_time_ms": 0,
                "period": {"from": date_from, "to": date_to},
            }
        total_fb = row["total_feedbacks"] or 1  # 0으로 나누기 방지
        return {
            "total_queries": row["total_queries"],
            "total_feedbacks": row["total_feedbacks"],
            "positive_rate": (row["positive_count"] or 0) / total_fb if row["total_feedbacks"] else 0,
            "negative_rate": (row["negative_count"] or 0) / total_fb if row["total_feedbacks"] else 0,
            "partial_rate": (row["partial_count"] or 0) / total_fb if row["total_feedbacks"] else 0,
            "avg_execution_time_ms": float(row["avg_execution_time_ms"] or 0),
            "period": {"from": date_from, "to": date_to},
        }

    async def get_trend(
        self, tenant_id: str, date_from: str, date_to: str, granularity: str = "day"
    ) -> list[dict]:
        """일별/주별 피드백 추이."""
        # SQL Injection 방지: 허용 목록 검증 (defense-in-depth)
        if granularity not in ("day", "week"):
            granularity = "day"
        trunc = granularity
        sql = f"""
        SELECT
            DATE_TRUNC('{trunc}', created_at)::date AS date,
            COUNT(*) FILTER (WHERE rating = 'positive') AS positive,
            COUNT(*) FILTER (WHERE rating = 'negative') AS negative,
            COUNT(*) FILTER (WHERE rating = 'partial') AS partial,
            COUNT(*) AS total
        FROM query_feedback
        WHERE tenant_id = $1
          AND created_at >= $2::date
          AND created_at < ($3::date + INTERVAL '1 day')
        GROUP BY DATE_TRUNC('{trunc}', created_at)
        ORDER BY date
        """
        rows = await self._fetch_all(sql, [tenant_id, date_from, date_to])
        return [
            {
                "date": str(r["date"]),
                "positive": r["positive"],
                "negative": r["negative"],
                "partial": r["partial"],
                "total": r["total"],
            }
            for r in rows
        ]

    async def get_failure_patterns(
        self, tenant_id: str, date_from: str, date_to: str, limit: int = 20
    ) -> list[dict]:
        """실패 쿼리 패턴 분석 — status='error' 그룹핑."""
        sql = """
        SELECT
            COALESCE(
                SUBSTRING(result::text FROM '"error":\\s*"([^"]+)"'),
                'Unknown Error'
            ) AS pattern,
            COUNT(*) AS count,
            MAX(created_at)::text AS last_occurred,
            (ARRAY_AGG(question ORDER BY created_at DESC))[1] AS example_question
        FROM query_history
        WHERE tenant_id = $1
          AND status = 'error'
          AND created_at >= $2::date
          AND created_at < ($3::date + INTERVAL '1 day')
        GROUP BY pattern
        ORDER BY count DESC
        LIMIT $4
        """
        rows = await self._fetch_all(sql, [tenant_id, date_from, date_to, limit])
        return [dict(r) for r in rows]

    async def get_datasource_breakdown(
        self, tenant_id: str, date_from: str, date_to: str
    ) -> list[dict]:
        """데이터소스별 쿼리 수 + 피드백 분포."""
        sql = """
        SELECT
            qh.datasource_id,
            COUNT(DISTINCT qh.id) AS total_queries,
            COUNT(fb.id) FILTER (WHERE fb.rating = 'positive') AS positive,
            COUNT(fb.id) FILTER (WHERE fb.rating = 'negative') AS negative,
            COUNT(fb.id) FILTER (WHERE fb.rating = 'partial') AS partial
        FROM query_history qh
        LEFT JOIN query_feedback fb ON fb.query_id = qh.id::text AND fb.tenant_id = qh.tenant_id
        WHERE qh.tenant_id = $1
          AND qh.created_at >= $2::date
          AND qh.created_at < ($3::date + INTERVAL '1 day')
        GROUP BY qh.datasource_id
        ORDER BY total_queries DESC
        """
        rows = await self._fetch_all(sql, [tenant_id, date_from, date_to])
        return [dict(r) for r in rows]

    async def get_top_failed_queries(
        self, tenant_id: str, date_from: str, date_to: str, limit: int = 10
    ) -> list[dict]:
        """가장 많이 negative 피드백 받은 질문 TOP-N."""
        sql = """
        SELECT
            qh.question,
            COUNT(*) AS negative_count,
            MAX(qh.sql) AS sql,
            MAX(qh.created_at)::text AS last_occurred
        FROM query_feedback fb
        JOIN query_history qh ON qh.id::text = fb.query_id AND qh.tenant_id = fb.tenant_id
        WHERE fb.tenant_id = $1
          AND fb.rating = 'negative'
          AND fb.created_at >= $2::date
          AND fb.created_at < ($3::date + INTERVAL '1 day')
        GROUP BY qh.question
        ORDER BY negative_count DESC
        LIMIT $4
        """
        rows = await self._fetch_all(sql, [tenant_id, date_from, date_to, limit])
        return [dict(r) for r in rows]

    async def get_feedback_list(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        rating: str | None = None,
        datasource_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        """피드백 목록 (페이지네이션)."""
        conditions = ["fb.tenant_id = $1"]
        params: list = [tenant_id]
        idx = 2

        if rating:
            conditions.append(f"fb.rating = ${idx}")
            params.append(rating)
            idx += 1
        if date_from:
            conditions.append(f"fb.created_at >= ${idx}::date")
            params.append(date_from)
            idx += 1
        if date_to:
            conditions.append(f"fb.created_at < (${idx}::date + INTERVAL '1 day')")
            params.append(date_to)
            idx += 1

        where = " AND ".join(conditions)

        # 카운트 쿼리
        count_sql = f"SELECT COUNT(*) AS cnt FROM query_feedback fb WHERE {where}"
        count_row = await self._fetch_one(count_sql, params)
        total_count = count_row["cnt"] if count_row else 0

        # 데이터 쿼리
        offset = (page - 1) * page_size
        data_sql = f"""
        SELECT
            fb.id::text AS id,
            COALESCE(qh.question, '') AS question,
            COALESCE(qh.sql, '') AS sql,
            fb.rating,
            fb.corrected_sql,
            fb.comment,
            fb.user_id::text AS user_id,
            COALESCE(qh.datasource_id, '') AS datasource_id,
            fb.created_at::text AS created_at
        FROM query_feedback fb
        LEFT JOIN query_history qh ON qh.id::text = fb.query_id AND qh.tenant_id = fb.tenant_id
        WHERE {where}
        ORDER BY fb.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([page_size, offset])
        rows = await self._fetch_all(data_sql, params)

        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        return {
            "items": [dict(r) for r in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
            },
        }


# 싱글톤 인스턴스
feedback_analytics = FeedbackAnalytics()
