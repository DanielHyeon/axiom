"""Value Mapping: 자연어 값 -> DB 값 매핑 서비스.

사용자가 "서울의 매출"이라고 질문하면, DB의 region='서울' 값으로
정확히 매핑해주는 3단계 파이프라인을 구현한다.

파이프라인:
  1단계: 인메모리 캐시 조회 (이전에 학습된 매핑)
  2단계: DB Probe — 실제 DB에서 ILIKE 검색 (파라미터 바인딩 필수)
  3단계: SQL WHERE 리터럴 검증

보안 주의:
  - DB Probe SQL에서 f-string 삽입 절대 금지 (C7 Critical)
  - 모든 사용자 입력은 파라미터 바인딩($1) 사용
  - col_name, table_name은 스키마 카탈로그에서 검증된 값만 허용
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------


class ValueMapping(BaseModel):
    """자연어 -> DB 값 매핑 전송 객체."""

    natural_value: str = Field(description="자연어에서 추출한 값")
    db_value: str = Field(description="실제 DB에 저장된 값")
    column_fqn: str = Field(description="컬럼 정규화 이름 (예: public.sales.region)")
    confidence: float = Field(
        default=1.0,
        description="신뢰도: 1.0=캐시 검증, 0.7~0.9=DB probe, <0.7=추론",
    )
    verified: bool = Field(default=False, description="품질 게이트 통과 여부")
    source: str = Field(default="", description="출처: cache | db_probe | neo4j_mapping")


@dataclass
class MappingResult:
    """단일 값 매핑 해석 결과."""

    db_value: str | None = None
    confidence: float = 0.0
    source: str = ""  # "cache" | "db_probe" | "neo4j_mapping"
    column_fqn: str = ""


@dataclass
class ResolvedValue:
    """해석 완료된 값 매핑."""

    user_term: str
    actual_value: str
    source: str  # "cache" | "db_probe" | "neo4j_mapping"
    column_fqn: str
    confidence: float


# ---------------------------------------------------------------------------
# 한국어 텍스트 처리 유틸리티
# ---------------------------------------------------------------------------

# 한국어 조사 목록 (긴 것부터 매칭해야 정확함)
_KOREAN_PARTICLES = (
    "에서", "으로", "의", "을", "를", "은", "는",
    "이", "가", "과", "와", "에", "로", "도", "만",
)

# 행정구역 접미사 (시/군/구/도/읍/면/동)
_KOREAN_ADMIN_SUFFIXES = ("시", "군", "구", "도", "읍", "면", "동")

# SQL WHERE 절에서 col='value' 패턴 추출용 정규식
_EQUALITY_FILTER_RE = re.compile(
    r"""
    ["']?(\w+)["']?\s*     # 컬럼명 (따옴표 있을 수 있음)
    =\s*                    # 등호
    '([^']*)'               # 값 (작은따옴표로 감싸진 문자열)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _strip_korean_particles(text: str) -> str:
    """한국어 조사를 제거한다.

    예: "서울의" -> "서울", "부산에서" -> "부산"
    """
    result = text.strip()
    if len(result) < 2:
        return result

    # 긴 조사부터 매칭 (예: "에서"를 "에" + "서"로 쪼개지지 않게)
    for particle in _KOREAN_PARTICLES:
        if result.endswith(particle) and len(result) > len(particle):
            result = result[: -len(particle)]
            break

    return result.strip()


def _strip_admin_suffix(text: str) -> str:
    """행정구역 접미사를 제거한다.

    예: "부산시" -> "부산", "경기도" -> "경기"
    """
    result = text.strip()
    if len(result) < 3:
        return result

    for suffix in _KOREAN_ADMIN_SUFFIXES:
        if result.endswith(suffix) and len(result) > len(suffix) + 1:
            return result[: -len(suffix)]

    return result


def expand_search_terms(terms: list[str]) -> list[str]:
    """한국어 조사/접미사 제거로 검색 범위를 확장한다.

    예: ["서울의", "부산시"] -> ["서울의", "서울", "부산시", "부산"]

    중복 제거 + 최대 20개까지만 반환한다.
    """
    expanded: list[str] = []
    seen: set[str] = set()

    for term in terms:
        candidates = [term]

        # 조사 제거 버전 추가
        stripped = _strip_korean_particles(term)
        if stripped != term:
            candidates.append(stripped)

        # 행정구역 접미사 제거 버전 추가
        admin_stripped = _strip_admin_suffix(term)
        if admin_stripped != term:
            candidates.append(admin_stripped)

        # 조사 + 행정구역 둘 다 제거한 버전
        double_stripped = _strip_admin_suffix(stripped)
        if double_stripped != term and double_stripped != stripped:
            candidates.append(double_stripped)

        for c in candidates:
            c = c.strip()
            if len(c) >= 2 and c.lower() not in seen:
                seen.add(c.lower())
                expanded.append(c)

    return expanded[:20]


# ---------------------------------------------------------------------------
# 스키마 카탈로그 검증
# ---------------------------------------------------------------------------

# 테이블명/컬럼명으로 허용되는 문자 패턴 (영문, 숫자, 언더스코어만)
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_safe_identifier(name: str) -> bool:
    """스키마 카탈로그에서 검증된 안전한 식별자인지 확인한다.

    SQL Injection 방지를 위해 테이블명/컬럼명에 허용되는 문자만 통과시킨다.
    """
    return bool(_SAFE_IDENTIFIER_RE.match(name))


# ---------------------------------------------------------------------------
# Value Mapping 서비스
# ---------------------------------------------------------------------------


class ValueMappingService:
    """자연어 -> DB 값 매핑 3단계 파이프라인.

    1단계: 인메모리 캐시 (이전에 학습된 매핑 재사용)
    2단계: DB Probe (실제 DB에서 ILIKE 검색, 파라미터 바인딩 필수)
    3단계: SQL WHERE 리터럴 검증
    """

    # DB Probe 제한 설정
    _PROBE_BUDGET = 2       # 최대 2번의 DB 쿼리
    _PROBE_TIMEOUT = 2.0    # 각 쿼리 최대 2초
    _PROBE_VALUE_LIMIT = 10  # 결과 최대 10건
    _PROBE_TABLE_LIMIT = 5   # 탐색 테이블 최대 5개

    # 캐시 최대 크기 — 초과 시 가장 오래된 항목부터 제거 (LRU 방식)
    _MAX_CACHE_SIZE: int = 5000

    # 텍스트 계열 데이터 타입 (DB Probe 대상)
    _TEXT_TYPES = frozenset({
        "varchar", "text", "character varying", "char", "character",
        "nvarchar", "ntext", "nchar", "bpchar",
    })

    def __init__(self) -> None:
        # 인메모리 캐시: (natural_value_lower, column_fqn_lower) -> MappingResult
        # OrderedDict를 사용하여 삽입 순서 유지 + LRU 제거 지원
        self._cache: OrderedDict[tuple[str, str], MappingResult] = OrderedDict()

    # -----------------------------------------------------------------------
    # 공개 API
    # -----------------------------------------------------------------------

    async def resolve_values(
        self,
        question: str,
        datasource_id: str,
        tenant_id: str,
        *,
        search_terms: list[str] | None = None,
        schema_catalog: list[Any] | None = None,
    ) -> list[ResolvedValue]:
        """3단계 값 해석 파이프라인을 수행한다.

        Args:
            question: 사용자 질문
            datasource_id: 데이터소스 ID
            tenant_id: 테넌트 ID
            search_terms: 명시적 검색 용어 (없으면 질문에서 추출)
            schema_catalog: 스키마 카탈로그 (DB Probe 시 사용)

        Returns:
            해석된 값 매핑 목록
        """
        resolved: list[ResolvedValue] = []
        resolved_terms: set[str] = set()

        # 검색 용어 추출 + 한국어 확장
        terms = search_terms or self._extract_search_terms(question)
        terms = expand_search_terms(terms)

        # --- 1단계: 인메모리 캐시 조회 ---
        for term in terms:
            cache_results = self._lookup_cache(term)
            for cr in cache_results:
                if cr.db_value and term.lower() not in resolved_terms:
                    resolved.append(ResolvedValue(
                        user_term=term,
                        actual_value=cr.db_value,
                        source="cache",
                        column_fqn=cr.column_fqn,
                        confidence=cr.confidence,
                    ))
                    resolved_terms.add(term.lower())

        # --- 2단계: DB Probe (미해석 용어만, budget 제한) ---
        unresolved = [t for t in terms if t.lower() not in resolved_terms]
        probes_used = 0

        for term in unresolved:
            if probes_used >= self._PROBE_BUDGET:
                break

            probed = await self._db_probe(
                term=term,
                datasource_id=datasource_id,
                tenant_id=tenant_id,
                schema_catalog=schema_catalog,
            )
            probes_used += 1

            if probed:
                resolved.append(probed)
                resolved_terms.add(term.lower())

                # 학습: 캐시에 저장
                self._save_to_cache(
                    natural_value=term,
                    db_value=probed.actual_value,
                    column_fqn=probed.column_fqn,
                    confidence=probed.confidence,
                )

        logger.info(
            "value_mapping_resolve",
            question_len=len(question),
            terms_count=len(terms),
            resolved_count=len(resolved),
            probes_used=probes_used,
        )

        return resolved

    def validate_sql_literals(
        self,
        sql: str,
        value_hints: dict[str, set[str]],
    ) -> list[dict[str, Any]]:
        """SQL WHERE 절의 리터럴이 실제 DB 값과 일치하는지 검증한다.

        Args:
            sql: 검증할 SQL 문
            value_hints: 컬럼명(소문자) -> 허용 값(소문자) 집합

        Returns:
            불일치 목록 [{column, value, allowed_sample}]
        """
        if not sql or not value_hints:
            return []

        mismatches: list[dict[str, Any]] = []
        for col, val in self._extract_equality_filters(sql):
            allowed = value_hints.get(col.lower())
            if allowed and val.lower() not in allowed:
                mismatches.append({
                    "column": col,
                    "value": val,
                    "allowed_sample": sorted(list(allowed))[:5],
                })

        if mismatches:
            logger.warning("sql_literal_mismatch", mismatches=mismatches)

        return mismatches

    async def save_learned_mapping(
        self,
        natural_value: str,
        db_value: str,
        column_fqn: str,
        verified: bool = False,
        confidence: float | None = None,
    ) -> None:
        """품질 게이트 통과 후 학습된 매핑을 저장한다.

        인메모리 캐시에 저장하고, Synapse ACL을 통해 Neo4j에도 저장한다.
        """
        # 인메모리 캐시 업데이트
        effective_confidence = confidence if confidence is not None else (1.0 if verified else 0.8)
        self._save_to_cache(
            natural_value=natural_value,
            db_value=db_value,
            column_fqn=column_fqn,
            confidence=effective_confidence,
        )

        # Neo4j에 저장 (Synapse ACL 경유, 비동기 best-effort)
        try:
            from app.infrastructure.acl.synapse_acl import oracle_synapse_acl
            await oracle_synapse_acl.save_value_mapping(
                natural_value=natural_value,
                code_value=db_value,
                column_fqn=column_fqn,
                verified=verified,
                verified_confidence=effective_confidence,
            )
        except Exception as exc:
            # Neo4j 저장 실패해도 인메모리 캐시는 유지
            logger.warning(
                "value_mapping_neo4j_save_failed",
                natural_value=natural_value,
                error=str(exc),
            )

    # -----------------------------------------------------------------------
    # 내부 메서드
    # -----------------------------------------------------------------------

    def _extract_search_terms(self, question: str) -> list[str]:
        """질문에서 검색 용어를 추출한다.

        공백으로 분리한 뒤, 길이 2 이상이고 숫자가 아닌 토큰만 선택한다.
        일반적인 질문 키워드(의, 은, 는 등)는 조사 제거 단계에서 처리한다.
        """
        # 질문부호, 마침표 등 구두점 제거
        cleaned = re.sub(r"[?!.,;:\"'()（）「」]", " ", question)
        tokens = cleaned.split()

        # 불용어 (질문 자체를 구성하는 단어들)
        stopwords = {
            "보여줘", "알려줘", "얼마", "어떤", "무엇", "뭐", "몇",
            "어디", "언제", "왜", "있나요", "있는지", "입니까",
            "해줘", "구해줘", "계산해줘", "조회해줘",
        }

        terms: list[str] = []
        for token in tokens:
            token = token.strip()
            if len(token) < 2:
                continue
            if token.lower() in stopwords:
                continue
            # 순수 숫자는 제외 (날짜 등은 검색 대상 아님)
            if token.isdigit():
                continue
            terms.append(token)

        return terms[:20]

    @staticmethod
    def _extract_equality_filters(sql: str) -> list[tuple[str, str]]:
        """SQL에서 col='value' 등호 필터를 추출한다.

        반환: [(column_name, value), ...]
        """
        if not sql:
            return []
        return _EQUALITY_FILTER_RE.findall(sql)

    def _lookup_cache(self, term: str) -> list[MappingResult]:
        """인메모리 캐시에서 매핑을 조회한다."""
        results: list[MappingResult] = []
        term_lower = term.lower()

        for (nat_val, col_fqn), mapping in self._cache.items():
            if nat_val == term_lower:
                results.append(mapping)

        return results

    def _save_to_cache(
        self,
        natural_value: str,
        db_value: str,
        column_fqn: str,
        confidence: float,
    ) -> None:
        """인메모리 캐시에 매핑을 저장한다.

        캐시 크기가 _MAX_CACHE_SIZE를 초과하면
        가장 오래된(먼저 삽입된) 항목을 제거한다.
        """
        key = (natural_value.lower(), column_fqn.lower())

        # 이미 존재하는 키면 순서를 갱신하기 위해 먼저 제거
        if key in self._cache:
            self._cache.move_to_end(key)

        self._cache[key] = MappingResult(
            db_value=db_value,
            confidence=confidence,
            source="cache",
            column_fqn=column_fqn,
        )

        # 캐시 크기 초과 시 가장 오래된 항목 제거 (FIFO/LRU)
        while len(self._cache) > self._MAX_CACHE_SIZE:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("value_mapping_cache_evict", key=evicted_key)

    async def _db_probe(
        self,
        term: str,
        datasource_id: str,
        tenant_id: str,
        schema_catalog: list[Any] | None = None,
    ) -> ResolvedValue | None:
        """제한적 DB 조회로 값을 탐색한다.

        보안 주의:
        - 파라미터 바인딩($1) 필수 (C7 Critical)
        - col_name, table_name은 스키마 카탈로그에서 검증된 안전한 식별자만 사용
        - 읽기 전용 SELECT + LIMIT 강제
        - 타임아웃 2초 하드 제한
        """
        from app.infrastructure.acl.synapse_acl import oracle_synapse_acl
        from app.core.sql_exec import sql_executor

        try:
            # 스키마 카탈로그에서 텍스트 컬럼 후보를 수집
            text_columns = await self._collect_text_columns(
                tenant_id=tenant_id,
                schema_catalog=schema_catalog,
            )

            if not text_columns:
                return None

            # 예산 내에서 DB Probe 수행
            for table_name, col_name, col_fqn in text_columns:
                # 식별자 안전성 검증 (SQL Injection 방지)
                if not _is_safe_identifier(table_name):
                    logger.warning("db_probe_unsafe_table", table_name=table_name)
                    continue
                if not _is_safe_identifier(col_name):
                    logger.warning("db_probe_unsafe_column", col_name=col_name)
                    continue

                # 파라미터 바인딩으로 안전한 SQL 구성 (C7 Critical 수정)
                # 테이블명/컬럼명은 위에서 검증된 안전한 식별자만 사용
                probe_sql = (
                    f'SELECT DISTINCT "{col_name}" '
                    f'FROM "{table_name}" '
                    f'WHERE "{col_name}" ILIKE $1 '
                    f'LIMIT {self._PROBE_VALUE_LIMIT}'
                )
                params = [f"%{term}%"]

                try:
                    # sql_executor를 통해 실행 (타임아웃 적용)
                    result = await sql_executor.execute_sql_with_params(
                        sql=probe_sql,
                        params=params,
                        datasource_id=datasource_id,
                        timeout_seconds=self._PROBE_TIMEOUT,
                    )

                    if result and result.rows:
                        matched_value = str(result.rows[0][0])
                        logger.info(
                            "db_probe_hit",
                            term=term,
                            matched=matched_value,
                            column=col_fqn,
                        )
                        return ResolvedValue(
                            user_term=term,
                            actual_value=matched_value,
                            source="db_probe",
                            column_fqn=col_fqn,
                            confidence=0.75,
                        )
                except Exception as exc:
                    logger.debug(
                        "db_probe_query_failed",
                        table=table_name,
                        column=col_name,
                        error=str(exc),
                    )
                    continue

        except Exception as exc:
            logger.warning("db_probe_failed", term=term, error=str(exc))

        return None

    async def _collect_text_columns(
        self,
        tenant_id: str,
        schema_catalog: list[Any] | None = None,
    ) -> list[tuple[str, str, str]]:
        """스키마 카탈로그에서 텍스트 타입 컬럼 목록을 수집한다.

        반환: [(table_name, column_name, column_fqn), ...]
        """
        from app.infrastructure.acl.synapse_acl import oracle_synapse_acl

        text_columns: list[tuple[str, str, str]] = []

        try:
            tables = await oracle_synapse_acl.list_tables(tenant_id=tenant_id)
        except Exception:
            tables = []

        for table_info in tables[: self._PROBE_TABLE_LIMIT]:
            try:
                detail = await oracle_synapse_acl.get_table_detail(
                    tenant_id=tenant_id,
                    table_name=table_info.name,
                )
                if not detail or not detail.columns:
                    continue

                for col in detail.columns:
                    dtype = (col.data_type or "").lower().strip()
                    if dtype in self._TEXT_TYPES or dtype == "":
                        col_fqn = f"{table_info.name}.{col.name}"
                        text_columns.append((table_info.name, col.name, col_fqn))

            except Exception:
                continue

        return text_columns


# ---------------------------------------------------------------------------
# 모듈 레벨 싱글턴
# ---------------------------------------------------------------------------

value_mapping_service = ValueMappingService()
