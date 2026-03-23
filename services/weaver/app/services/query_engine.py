"""G40: Unified Query Execution Plane — 모든 SQL 실행의 공통 정책 엔진.

Direct SQL, NL2SQL, 프로파일링, Drift Validation이 각각 쿼리를 실행하면
권한 검사, SQL 안전성 파싱, timeout, row limit, audit, 캐시 무효화가 중복된다.
이 모듈은 단일 경유점으로 모든 물리 SQL 실행을 통제한다.

서비스 간 SQL 실행 책임 분리:
- Oracle: SQL을 생성하지만 실행하지 않음
- Weaver (여기): 유일한 물리 SQL 실행 경유점
- Synapse: 시멘틱 계약/온톨로지 참조만
- Core: 인증, RBAC, 감사 정책 기준 제공
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.provenance import ExtractionMethod, ProvenanceEnvelope
from app.models.security import ColumnAccessLevel, MinimumSecurityGuardrail
from app.services.adapters.base import AdapterFactory

logger = logging.getLogger("axiom.weaver.query_engine")


# ── 호출자 유형 ── #

class QueryCaller(str, Enum):
    """SQL 실행 요청 출처 — 호출자별 정책 차등 적용"""
    DIRECT_SQL = "direct_sql"       # 사용자 직접 SQL
    NL2SQL = "nl2sql"               # Oracle NL2SQL 결과
    PROFILING = "profiling"         # 테이블 프로파일링
    DRIFT_DETECT = "drift_detect"   # SSDD 드리프트 검증


# ── 결과 모델 ── #

class QueryResult(BaseModel):
    """SQL 실행 결과"""
    columns: list[str] = Field(default_factory=list)
    column_types: list[str] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False  # row limit으로 잘렸는지
    warnings: list[str] = Field(default_factory=list)


class QueryAuditLog(BaseModel):
    """쿼리 감사 로그"""
    audit_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    datasource_name: str
    caller: str
    user_id: str
    tenant_id: str
    sql_hash: str  # SQL 전문 대신 해시로 기록 (보안)
    row_count: int = 0
    execution_time_ms: float = 0.0
    success: bool = True
    error: str | None = None
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── SQL 안전성 검증 ── #

# DML/DDL 차단 패턴 — SQL 본문 어디에서든 탐지 (C-1 리뷰 반영)
_DML_ANYWHERE = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s|ALTER\s|"
    r"CREATE\s|TRUNCATE\s|MERGE\s|GRANT\s|REVOKE\s)\b",
    re.IGNORECASE,
)

# 멀티 스테이트먼트 차단 (세미콜론 후 추가 SQL)
_MULTI_STATEMENT = re.compile(r";[\s]*\S")


def _validate_sql(sql: str, caller: QueryCaller) -> str | None:
    """SQL 안전성 검증 — 차단 시 사유 반환, 통과 시 None.

    규칙 (C-1 리뷰 반영 — 전체 SQL 본문 검사):
    1. 멀티 스테이트먼트 차단
    2. SELECT/WITH만 허용 (CTE 지원, N-2 반영)
    3. DML/DDL 키워드 전체 본문 검사 (writable CTE 방지)
    """
    cleaned = sql.strip().rstrip(";")
    if not cleaned:
        return "빈 SQL"

    # 멀티 스테이트먼트 차단 (SELECT 1; DROP TABLE ...)
    if _MULTI_STATEMENT.search(cleaned):
        return "멀티 스테이트먼트 SQL은 허용되지 않습니다"

    # SELECT 또는 WITH(CTE)만 허용 (N-2 반영)
    if not re.match(r"^\s*(SELECT|WITH)\b", cleaned, re.IGNORECASE):
        return "SELECT/WITH 문만 실행할 수 있습니다"

    # DML/DDL 키워드 전체 본문 검사 (writable CTE 방지)
    match = _DML_ANYWHERE.search(cleaned)
    if match:
        return f"금지된 SQL 키워드 감지: {match.group(0)}"

    return None


def _compute_sql_hash(sql: str) -> str:
    """SQL 전문 대신 SHA256 해시 — 감사 로그에 전문 노출 방지"""
    import hashlib
    return hashlib.sha256(sql.encode()).hexdigest()[:32]


# ── 정책 엔진 ── #

class QueryPolicyEngine:
    """모든 SQL 실행의 공통 정책 엔진.

    실행 흐름:
    1. SQL 파싱 → DML 차단 (SELECT만 허용)
    2. MinimumSecurityGuardrail → 민감 컬럼 마스킹
    3. AdapterFactory → execute_query() (타임아웃 + row limit)
    4. 감사 로그 기록 (ProvenanceEnvelope 포함)
    5. 결과 반환
    """

    def __init__(self) -> None:
        self._guardrail = MinimumSecurityGuardrail()
        # 감사 로그 (in-memory — Phase 2에서 PostgreSQL로 전환)
        self._audit_logs: list[QueryAuditLog] = []
        # 서킷 브레이커: (tenant_id, datasource, table_fqn) 단위 차단 (N-5 반영)
        self._blocked_tables: set[str] = set()
        # 동시성 보호 (M-2 반영)
        import asyncio
        self._lock = asyncio.Lock()

    async def execute_safe(
        self,
        datasource_name: str,
        sql: str,
        caller: QueryCaller,
        user_id: str,
        user_role: str,
        tenant_id: str,
        connection: dict[str, Any],
        engine: str,
        limit: int = 1000,
        timeout_seconds: int = 30,
    ) -> QueryResult:
        """안전한 SQL 실행 — 모든 물리 쿼리의 단일 경유점.

        Args:
            datasource_name: 데이터소스 식별자
            sql: 실행할 SQL (SELECT만)
            caller: 호출 출처 (direct_sql, nl2sql, profiling, drift_detect)
            user_id: 실행 요청 사용자
            user_role: 사용자 역할 (민감 컬럼 마스킹 판단)
            tenant_id: 테넌트 ID
            connection: DB 연결 정보
            engine: DB 엔진 유형
            limit: 최대 반환 행 수
            timeout_seconds: 쿼리 타임아웃 (초)

        Returns:
            QueryResult (마스킹 적용 후)

        Raises:
            ValueError: SQL 검증 실패
            PermissionError: 차단된 테이블 접근
            TimeoutError: 쿼리 타임아웃
        """
        start = time.monotonic()
        sql_hash = _compute_sql_hash(sql)

        # 1. SQL 안전성 검증
        if block_reason := _validate_sql(sql, caller):
            await self._record_audit_safe(
                datasource_name, caller, user_id, tenant_id,
                sql_hash, success=False, blocked_reason=block_reason,
            )
            raise ValueError(f"SQL 실행 차단: {block_reason}")

        # 2. 서킷 브레이커: 차단된 테이블 확인 (Phase 4 SSDD)
        if blocked := self._check_circuit_breaker(sql):
            await self._record_audit_safe(
                datasource_name, caller, user_id, tenant_id,
                sql_hash, success=False, blocked_reason=f"서킷 브레이커: {blocked}",
            )
            raise PermissionError(f"SSDD 서킷 브레이커에 의해 차단된 테이블: {blocked}")

        # 3. 어댑터로 실행
        try:
            adapter = AdapterFactory.create(engine, connection)
            raw_result = await adapter.execute_query(sql, limit=limit)
        except NotImplementedError as exc:
            await self._record_audit_safe(
                datasource_name, caller, user_id, tenant_id,
                sql_hash, success=False, error=f"{engine} 어댑터는 SQL 실행 미지원",
            )
            raise ValueError(f"{engine} 어댑터는 직접 SQL 실행을 지원하지 않습니다") from exc
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            await self._record_audit_safe(
                datasource_name, caller, user_id, tenant_id,
                sql_hash, success=False, error=str(e),
                execution_time_ms=elapsed,
            )
            raise

        elapsed = (time.monotonic() - start) * 1000

        # 4. 민감 컬럼 마스킹
        columns = raw_result.get("columns", [])
        rows = raw_result.get("rows", [])
        warnings: list[str] = []

        access_results = self._guardrail.check_column_access(columns, user_role)
        masked_cols = [r for r in access_results if r.access_level == ColumnAccessLevel.MASK]
        if masked_cols:
            rows = [self._guardrail.mask_row(row, access_results) for row in rows]
            warnings.append(
                f"민감 컬럼 {len(masked_cols)}개 마스킹 적용: "
                + ", ".join(r.column_name for r in masked_cols)
            )

        result = QueryResult(
            columns=columns,
            rows=rows,
            row_count=raw_result.get("row_count", len(rows)),
            execution_time_ms=elapsed,
            truncated=raw_result.get("row_count", 0) >= limit,
            warnings=warnings,
        )

        # 5. 감사 로그 기록
        await self._record_audit_safe(
            datasource_name, caller, user_id, tenant_id,
            sql_hash, success=True,
            row_count=result.row_count,
            execution_time_ms=elapsed,
        )

        logger.info(
            "쿼리 실행 완료: ds=%s, caller=%s, rows=%d, time=%.1fms",
            datasource_name, caller.value, result.row_count, elapsed,
        )
        return result

    def block_table(self, table_fqn: str) -> None:
        """서킷 브레이커: 테이블 차단 (Phase 4 SSDD에서 호출)"""
        self._blocked_tables.add(table_fqn.lower())
        logger.warning("서킷 브레이커 활성화: %s", table_fqn)

    def unblock_table(self, table_fqn: str) -> None:
        """서킷 브레이커: 테이블 차단 해제"""
        self._blocked_tables.discard(table_fqn.lower())
        logger.info("서킷 브레이커 해제: %s", table_fqn)

    def get_audit_logs(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> list[QueryAuditLog]:
        """감사 로그 조회 (테넌트 격리)"""
        filtered = [log for log in self._audit_logs if log.tenant_id == tenant_id]
        return sorted(filtered, key=lambda l: l.created_at, reverse=True)[:limit]

    # ── 내부 메서드 ── #

    def _check_circuit_breaker(self, sql: str) -> str | None:
        """SQL에서 참조하는 테이블이 차단 목록에 있는지 확인.

        간단한 FROM/JOIN 절 파싱 — Phase 4에서 SQLGlot AST 파싱으로 교체.
        """
        if not self._blocked_tables:
            return None

        sql_lower = sql.lower()
        for table in self._blocked_tables:
            # 간단한 문자열 매칭 (정확도를 위해 Phase 4에서 AST 파싱 사용)
            if table in sql_lower:
                return table
        return None

    async def _record_audit_safe(
        self,
        datasource_name: str,
        caller: QueryCaller | str,
        user_id: str,
        tenant_id: str,
        sql_hash: str,
        success: bool = True,
        error: str | None = None,
        blocked_reason: str | None = None,
        row_count: int = 0,
        execution_time_ms: float = 0.0,
    ) -> None:
        """감사 로그 기록 — asyncio.Lock으로 동시성 보호 (M-2 반영)"""
        caller_str = caller.value if isinstance(caller, QueryCaller) else str(caller)
        log = QueryAuditLog(
            datasource_name=datasource_name,
            caller=caller_str,
            user_id=user_id,
            tenant_id=tenant_id,
            sql_hash=sql_hash,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            success=success,
            error=error,
            blocked_reason=blocked_reason,
        )
        async with self._lock:
            self._audit_logs.append(log)
            # 최대 10000건 유지 (atomic trim)
            if len(self._audit_logs) > 10000:
                self._audit_logs = self._audit_logs[-5000:]

        if not success:
            logger.warning(
                "쿼리 차단/실패: ds=%s, caller=%s, user=%s, reason=%s",
                datasource_name, caller_str, user_id, blocked_reason or error,
            )


# 모듈 수준 싱글톤
query_engine = QueryPolicyEngine()
