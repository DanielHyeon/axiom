"""G31: Identity Profile + IdentityResolver — 다중 소스 동일 엔티티 식별.

동일한 테이블 정의가 DDL 파일, Java Entity, 운영 DB에 각각 존재할 때
별개의 노드로 생성되면 그래프가 오염된다.
이 모듈은 "이것이 동일 엔티티인지" 판별하고 "어느 소스가 권위(SoT)인지" 결정한다.

설계 원칙:
- canonical_name(schema.table)으로 기존 노드 검색
- identity_hash(구조 해시)로 구조적 동일성 비교
- SoT는 기본 우선순위 + 자산별 override 정책으로 결정
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.provenance import ExtractionMethod
from app.services.adapters.normalization import StandardColumnMetadata, StandardTableMetadata

logger = logging.getLogger("axiom.weaver.identity")


# ── 관계 상태 ── #

class RelationStatus(str, Enum):
    """관계 상태 — 소스-DB 간 매핑의 생명주기"""
    PROPOSED = "proposed"             # 시스템이 자동 제안 (LLM 추론 등)
    USER_CONFIRMED = "user_confirmed" # 사용자가 명시적으로 확정
    AUTO_VERIFIED = "auto_verified"   # 시스템이 자동 검증 (이름+구조 일치)
    SUPERSEDED = "superseded"         # 신규 버전으로 대체됨
    REJECTED = "rejected"             # 사용자가 거부


class SourceOfTruth(str, Enum):
    """권위 소스 — 높을수록 우선"""
    LIVE_DATABASE = "live_database"   # 우선순위 1: 실시간 DB 스키마
    DDL_FILE = "ddl_file"             # 우선순위 2: 공식 DDL
    SOURCE_CODE = "source_code"       # 우선순위 3: 소스코드 분석 결과
    MINDSDB = "mindsdb"               # 우선순위 4: MindsDB 페더레이션
    MANUAL = "manual"                 # 우선순위 5: 수동 입력


# ── SoT Override 정책 ── #

class SoTOverridePolicy(BaseModel):
    """자산별 SoT 예외 규칙.

    예: 마이그레이션 중 DDL이 운영 DB보다 권위 있는 경우
    """
    scope_type: Literal["datasource", "schema", "table", "column"]
    scope_key: str                    # 예: "pg_prod.public.orders"
    preferred_method: ExtractionMethod
    reason: str                       # 예: "v2.1 마이그레이션 중, DDL이 최신"
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None  # 만료 시 기본 규칙으로 복귀


# ── Identity Profile ── #

class IdentitySource(BaseModel):
    """하나의 추출 경로에서 발견된 소스 정보"""
    method: ExtractionMethod
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_ref: str = ""              # 파일 경로, 데이터소스명, 또는 upload_id
    column_count: int = 0
    structure_hash: str = ""          # 이 소스에서의 구조 해시
    is_approved: bool = False         # 승인된 provenance 존재 여부


class IdentityProfile(BaseModel):
    """테이블/컬럼의 신원 프로파일 — 다중 소스에서 동일 엔티티 식별"""
    canonical_name: str               # 정규화된 이름 (schema.table)
    sources: list[IdentitySource] = Field(default_factory=list)
    primary_source: SourceOfTruth = SourceOfTruth.MANUAL
    identity_hash: str = ""           # 구조 해시 (컬럼명+타입 정렬 후 SHA256)
    merged_at: datetime | None = None


# ── Identity Resolver ── #

class IdentityResolution(BaseModel):
    """동일성 판정 결과"""
    action: Literal["merged", "proposed", "created"]  # 병합/제안/신규
    canonical_name: str
    identity_hash: str
    primary_source: SourceOfTruth
    confidence: float = 1.0


# 기본 SoT 우선순위
_DEFAULT_PRIORITY: dict[ExtractionMethod, int] = {
    ExtractionMethod.NATIVE_INTROSPECTION: 1,
    ExtractionMethod.DDL_PARSE: 2,
    ExtractionMethod.CODE_ANALYSIS: 3,
    ExtractionMethod.MINDSDB_FEDERATION: 4,
    ExtractionMethod.DOCUMENT_EXTRACTION: 5,
    ExtractionMethod.MANUAL: 6,
    ExtractionMethod.STANDARD_INGESTION: 7,
}

# ExtractionMethod → SourceOfTruth 매핑
_METHOD_TO_SOT: dict[ExtractionMethod, SourceOfTruth] = {
    ExtractionMethod.NATIVE_INTROSPECTION: SourceOfTruth.LIVE_DATABASE,
    ExtractionMethod.DDL_PARSE: SourceOfTruth.DDL_FILE,
    ExtractionMethod.CODE_ANALYSIS: SourceOfTruth.SOURCE_CODE,
    ExtractionMethod.MINDSDB_FEDERATION: SourceOfTruth.MINDSDB,
    ExtractionMethod.MANUAL: SourceOfTruth.MANUAL,
    ExtractionMethod.DOCUMENT_EXTRACTION: SourceOfTruth.MANUAL,
    ExtractionMethod.STANDARD_INGESTION: SourceOfTruth.MANUAL,
}


class IdentityResolver:
    """다중 소스에서 발견된 테이블을 동일 엔티티로 병합.

    사용법:
        resolver = IdentityResolver()
        result = resolver.resolve(table, ExtractionMethod.DDL_PARSE, "ddl/orders.sql")
    """

    def __init__(self) -> None:
        # in-memory 프로파일 저장소 (Phase 1에서 Neo4j/PostgreSQL로 전환)
        self._profiles: dict[str, IdentityProfile] = {}
        self._overrides: list[SoTOverridePolicy] = []

    def add_override(self, policy: SoTOverridePolicy) -> None:
        """SoT override 정책 추가.

        주의: 현재 scope 매칭은 method 수준만 구현됨.
        scope_type/scope_key 기반 세밀한 매칭은 Phase 1 Sprint 3에서 구현 예정.
        """
        logger.warning(
            "SoT override 추가: scope=%s:%s, method=%s — "
            "주의: 현재 scope 매칭은 method 수준만 지원됩니다",
            policy.scope_type, policy.scope_key, policy.preferred_method.value,
        )
        self._overrides.append(policy)

    def resolve(
        self,
        table: StandardTableMetadata,
        method: ExtractionMethod,
        source_ref: str,
        schema_name: str = "public",
    ) -> IdentityResolution:
        """동일 엔티티 판별 + 병합/제안/신규 결정.

        1. canonical_name으로 기존 프로파일 검색
        2. identity_hash 비교 (구조적 동일성)
        3. 동일 → 기존 프로파일에 source 추가 + SoT 재평가 (merged)
        4. 유사 (이름만 같고 구조 다름) → PROPOSED 상태 (proposed)
        5. 신규 → 새 프로파일 생성 (created)
        """
        canonical = f"{schema_name}.{table.name}"
        new_hash = self._compute_structure_hash(table.columns)
        now = datetime.now(timezone.utc)

        new_source = IdentitySource(
            method=method,
            discovered_at=now,
            source_ref=source_ref,
            column_count=len(table.columns),
            structure_hash=new_hash,
        )

        existing = self._profiles.get(canonical)

        if existing:
            if existing.identity_hash == new_hash:
                # 구조 동일 → 병합
                existing.sources.append(new_source)
                existing.merged_at = now
                existing.primary_source = self._evaluate_sot(existing.sources)
                logger.info("엔티티 병합: %s (source=%s)", canonical, method.value)
                return IdentityResolution(
                    action="merged",
                    canonical_name=canonical,
                    identity_hash=new_hash,
                    primary_source=existing.primary_source,
                    confidence=1.0,
                )
            else:
                # 이름은 같지만 구조가 다름 → 사용자 확인 필요
                existing.sources.append(new_source)
                logger.warning("구조 불일치 감지: %s (기존 hash=%s, 신규 hash=%s)",
                               canonical, existing.identity_hash[:8], new_hash[:8])
                return IdentityResolution(
                    action="proposed",
                    canonical_name=canonical,
                    identity_hash=new_hash,
                    primary_source=existing.primary_source,
                    confidence=0.6,  # 이름 매칭이지만 구조 불일치
                )
        else:
            # 신규 엔티티
            profile = IdentityProfile(
                canonical_name=canonical,
                sources=[new_source],
                primary_source=self._evaluate_sot([new_source]),
                identity_hash=new_hash,
            )
            self._profiles[canonical] = profile
            logger.info("신규 엔티티 등록: %s (source=%s)", canonical, method.value)
            return IdentityResolution(
                action="created",
                canonical_name=canonical,
                identity_hash=new_hash,
                primary_source=profile.primary_source,
                confidence=1.0,
            )

    def _compute_structure_hash(self, columns: list[StandardColumnMetadata]) -> str:
        """컬럼명+타입+nullable+pk 정렬 후 SHA256 — 순서 무관 구조 비교.

        nullable/pk 포함으로 NOT NULL→NULL 변경도 감지 (리뷰 #5 반영)
        """
        normalized = sorted(
            f"{c.name}:{c.data_type}:{'N' if c.nullable else 'NN'}:{'PK' if c.is_primary_key else ''}"
            for c in columns
        )
        return hashlib.sha256("|".join(normalized).encode()).hexdigest()

    def _evaluate_sot(
        self,
        sources: list[IdentitySource],
    ) -> SourceOfTruth:
        """SoT 결정: 기본 우선순위 + override 정책 + 승인 여부 + 최신성"""
        if not sources:
            return SourceOfTruth.MANUAL

        # override 정책 확인 (TODO: scope 매칭 구현)
        for ov in self._overrides:
            for s in sources:
                if s.method == ov.preferred_method:
                    # 만료 체크
                    if ov.expires_at and datetime.now(timezone.utc) > ov.expires_at:
                        continue
                    return _METHOD_TO_SOT.get(ov.preferred_method, SourceOfTruth.MANUAL)

        # 기본 규칙: 우선순위 > 승인 여부 > 최신성
        best = min(sources, key=lambda s: (
            _DEFAULT_PRIORITY.get(s.method, 99),
            0 if s.is_approved else 1,
            -s.discovered_at.timestamp(),
        ))
        return _METHOD_TO_SOT.get(best.method, SourceOfTruth.MANUAL)

    def get_profile(self, canonical_name: str) -> IdentityProfile | None:
        """프로파일 조회"""
        return self._profiles.get(canonical_name)

    def list_profiles(self) -> list[IdentityProfile]:
        """전체 프로파일 목록"""
        return list(self._profiles.values())
