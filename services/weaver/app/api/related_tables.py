"""G12: 관련 테이블 자동 발견 엔드포인트.

FK 관계 + 이름 유사도 기반으로 관련 테이블을 랭킹하여 반환한다.
ERD 자동 연결, 데이터 탐색 시 "이 테이블과 관련된 테이블" 추천에 사용.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.adapters.base import AdapterFactory

logger = logging.getLogger("axiom.weaver.api.related_tables")

router = APIRouter(prefix="/api/v3/weaver", tags=["related-tables"])

_auth = AuthService()

# M-5: related-tables도 analyst 이상만 사용 가능
_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class RelatedTable(BaseModel):
    """관련 테이블 정보"""
    table_name: str
    schema_name: str = ""
    relation_type: str             # "fk_direct", "fk_reverse", "name_similarity"
    score: float = 0.0             # 관련성 점수 (0.0 ~ 1.0)
    fk_columns: list[dict] = Field(default_factory=list)  # FK 연결 컬럼 정보
    similarity_detail: str = ""    # 유사도 근거 설명


class RelatedTablesRequest(BaseModel):
    """관련 테이블 발견 요청"""
    datasource_name: str
    engine: str
    connection: dict[str, Any]
    table_name: str
    schema_name: str = "public"
    limit: int = Field(default=10, ge=1, le=50)


class RelatedTablesResponse(BaseModel):
    success: bool = True
    data: list[RelatedTable]
    total: int


# ── 유사도 계산 ── #

def _name_similarity(name1: str, name2: str) -> float:
    """테이블 이름 유사도 — SequenceMatcher + 접두사 보너스"""
    if name1 == name2:
        return 0.0  # 자기 자신 제외

    n1 = name1.lower()
    n2 = name2.lower()

    # 기본 시퀀스 유사도
    base_score = SequenceMatcher(None, n1, n2).ratio()

    # 접두사 매칭 보너스 (예: orders ↔ order_items)
    prefix_len = 0
    for c1, c2 in zip(n1, n2):
        if c1 == c2:
            prefix_len += 1
        else:
            break
    # 접두사가 이름의 50% 이상이면 보너스
    min_len = min(len(n1), len(n2))
    if min_len > 0 and prefix_len / min_len >= 0.5:
        base_score = min(1.0, base_score + 0.15)

    # _id, _type 등 공통 접미사 패턴
    suffixes = ["_id", "_type", "_code", "_name", "_date"]
    for suffix in suffixes:
        # 한쪽이 다른 쪽의 base + suffix인 경우 (예: user ↔ user_id → 매우 관련)
        if n1.replace(suffix, "") == n2 or n2.replace(suffix, "") == n1:
            base_score = max(base_score, 0.7)

    return round(base_score, 3)


# ── 엔드포인트 ── #

@router.post("/related-tables")
async def discover_related_tables(
    request: RelatedTablesRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> RelatedTablesResponse:
    """FK + 이름 유사도 기반 관련 테이블 랭킹.

    랭킹 기준:
    1. FK 직접 연결 (source→target) → score 1.0
    2. FK 역방향 연결 (target→source) → score 0.9
    3. 이름 유사도 (SequenceMatcher + 접두사 보너스) → score 0.3~0.8
    """
    # M-5: 역할 검증
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="관련 테이블 발견은 analyst 이상 역할만 사용 가능합니다",
        )

    try:
        adapter = AdapterFactory.create(request.engine, request.connection)

        # 1. FK 관계 조회
        fks = await adapter.get_foreign_keys(request.schema_name)

        # 2. 전체 테이블 목록 (이름 유사도용)
        tables = await adapter.get_tables(request.schema_name)
        all_table_names = [t.get("name", "") for t in tables]

        # 3. 관련 테이블 수집
        related: dict[str, RelatedTable] = {}  # table_name → RelatedTable (중복 방지)

        # 3a. FK 직접 연결 (이 테이블이 source)
        for fk in fks:
            if fk.get("source_table") == request.table_name:
                target = fk.get("target_table", "")
                if target and target != request.table_name:
                    key = target
                    existing = related.get(key)
                    if existing:
                        # 이미 FK로 등록됨 — 컬럼 정보 추가
                        existing.fk_columns.append({
                            "source_column": fk.get("source_column", ""),
                            "target_column": fk.get("target_column", ""),
                            "constraint": fk.get("constraint_name", ""),
                        })
                    else:
                        related[key] = RelatedTable(
                            table_name=target,
                            schema_name=request.schema_name,
                            relation_type="fk_direct",
                            score=1.0,
                            fk_columns=[{
                                "source_column": fk.get("source_column", ""),
                                "target_column": fk.get("target_column", ""),
                                "constraint": fk.get("constraint_name", ""),
                            }],
                        )

        # 3b. FK 역방향 연결 (이 테이블이 target)
        for fk in fks:
            if fk.get("target_table") == request.table_name:
                source = fk.get("source_table", "")
                if source and source != request.table_name:
                    key = source
                    existing = related.get(key)
                    if existing:
                        # 이미 직접 FK로 등록된 경우 score 유지
                        if existing.relation_type != "fk_direct":
                            existing.fk_columns.append({
                                "source_column": fk.get("source_column", ""),
                                "target_column": fk.get("target_column", ""),
                                "constraint": fk.get("constraint_name", ""),
                            })
                    else:
                        related[key] = RelatedTable(
                            table_name=source,
                            schema_name=request.schema_name,
                            relation_type="fk_reverse",
                            score=0.9,
                            fk_columns=[{
                                "source_column": fk.get("source_column", ""),
                                "target_column": fk.get("target_column", ""),
                                "constraint": fk.get("constraint_name", ""),
                            }],
                        )

        # 3c. 이름 유사도 (FK에 없는 테이블만)
        for tname in all_table_names:
            if tname == request.table_name or tname in related:
                continue
            sim = _name_similarity(request.table_name, tname)
            # 최소 유사도 임계값 (0.35 이상만 포함)
            if sim >= 0.35:
                related[tname] = RelatedTable(
                    table_name=tname,
                    schema_name=request.schema_name,
                    relation_type="name_similarity",
                    score=round(sim * 0.8, 3),  # 0.8 가중치 적용 (FK보다 낮게)
                    similarity_detail=f"이름 유사도: {sim:.1%}",
                )

        # 4. 점수 기준 정렬 + limit 적용
        sorted_related = sorted(related.values(), key=lambda r: r.score, reverse=True)
        result = sorted_related[:request.limit]

        return RelatedTablesResponse(data=result, total=len(result))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("관련 테이블 발견 실패: %s.%s", request.schema_name, request.table_name)
        # M-6: 내부 오류 상세 노출 방지
        raise HTTPException(status_code=500, detail="관련 테이블 발견 중 내부 오류 발생") from e
