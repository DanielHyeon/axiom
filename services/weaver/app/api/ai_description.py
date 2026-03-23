"""G21: LLM 메타데이터 설명 자동 생성 API.

테이블/컬럼 이름과 데이터 샘플에서 비즈니스 설명을 자동 생성한다.
MVP: 규칙 기반 템플릿 (Phase 4에서 LLM API 연동).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser

logger = logging.getLogger("axiom.weaver.api.ai_description")

router = APIRouter(prefix="/api/v3/weaver/ai-description", tags=["ai-description"])

_auth = AuthService()
_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class DescriptionRequest(BaseModel):
    """설명 생성 요청"""
    entity_type: str = "table"            # table, column
    entity_name: str                      # 테이블명 또는 컬럼명
    table_name: str = ""                  # 컬럼인 경우 소속 테이블
    data_type: str = ""                   # 컬럼 데이터 타입
    sample_values: list[str] = Field(default_factory=list, max_length=20)
    context: str = ""                     # 추가 컨텍스트 (스키마명, 도메인 등)


class DescriptionResult(BaseModel):
    """설명 생성 결과"""
    entity_name: str
    suggested_description: str            # AI가 제안한 설명
    suggested_description_en: str = ""    # 영어 설명
    confidence: float = 0.5
    generation_method: str = "rule_based" # rule_based | llm


# ── 규칙 기반 설명 생성기 (MVP) ── #

# 공통 약어/패턴 → 설명 매핑
_COMMON_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^id$", re.I), "고유 식별자", "Unique identifier"),
    (re.compile(r"_id$", re.I), "{base} 참조 키", "{base} reference key"),
    (re.compile(r"^created_at$", re.I), "생성 일시", "Creation timestamp"),
    (re.compile(r"^updated_at$", re.I), "수정 일시", "Last update timestamp"),
    (re.compile(r"^deleted_at$", re.I), "삭제 일시 (소프트 삭제)", "Soft deletion timestamp"),
    (re.compile(r"^is_", re.I), "{name} 여부 플래그", "{name} boolean flag"),
    (re.compile(r"^has_", re.I), "{name} 보유 여부", "{name} possession flag"),
    (re.compile(r"^(name|title)$", re.I), "이름/제목", "Name or title"),
    (re.compile(r"^(email|mail)$", re.I), "이메일 주소", "Email address"),
    (re.compile(r"^(phone|mobile|tel)", re.I), "전화번호", "Phone number"),
    (re.compile(r"^(price|cost|amount|total)", re.I), "금액/비용", "Price or cost amount"),
    (re.compile(r"^(qty|quantity|count)", re.I), "수량", "Quantity or count"),
    (re.compile(r"^(status|state)", re.I), "상태 코드", "Status code"),
    (re.compile(r"^(description|desc|memo|note)", re.I), "설명/메모", "Description or note"),
    (re.compile(r"^(address|addr)", re.I), "주소", "Address"),
    (re.compile(r"^(start|begin)_", re.I), "{base} 시작", "{base} start"),
    (re.compile(r"^(end|finish)_", re.I), "{base} 종료", "{base} end"),
]

# 테이블 이름 패턴
_TABLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(user|member|account)", re.I), "사용자/회원 정보 테이블"),
    (re.compile(r"^(order|purchase)", re.I), "주문/구매 정보 테이블"),
    (re.compile(r"^(product|item|goods)", re.I), "상품/제품 정보 테이블"),
    (re.compile(r"^(payment|billing)", re.I), "결제/청구 정보 테이블"),
    (re.compile(r"^(log|audit|history)", re.I), "로그/이력 테이블"),
    (re.compile(r"^(config|setting|preference)", re.I), "설정/구성 테이블"),
]


def _generate_column_description(name: str, data_type: str, table_name: str) -> tuple[str, str]:
    """컬럼명에서 한글/영어 설명 추론"""
    base = name.replace("_id", "").replace("_", " ").strip()

    for pattern, ko_template, en_template in _COMMON_PATTERNS:
        if pattern.search(name):
            ko = ko_template.replace("{base}", base).replace("{name}", name)
            en = en_template.replace("{base}", base).replace("{name}", name)
            return ko, en

    # 기본: 이름 기반 설명
    display = name.replace("_", " ").title()
    return f"{display} 값", f"{display} value"


def _generate_table_description(name: str) -> tuple[str, str]:
    """테이블명에서 한글/영어 설명 추론"""
    for pattern, ko_desc in _TABLE_PATTERNS:
        if pattern.search(name):
            return ko_desc, f"{name.replace('_', ' ').title()} table"

    display = name.replace("_", " ").title()
    return f"{display} 데이터 테이블", f"{display} data table"


# ── 엔드포인트 ── #

@router.post("/generate")
async def generate_description(
    request: DescriptionRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """테이블/컬럼의 비즈니스 설명 자동 생성.

    MVP: 규칙 기반 패턴 매칭. Phase 4에서 LLM 연동.
    """
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    if request.entity_type == "column":
        ko, en = _generate_column_description(
            request.entity_name, request.data_type, request.table_name,
        )
        confidence = 0.6
    else:
        ko, en = _generate_table_description(request.entity_name)
        confidence = 0.5

    # 샘플 값이 있으면 신뢰도 약간 상승
    if request.sample_values:
        confidence = min(confidence + 0.1, 0.8)

    result = DescriptionResult(
        entity_name=request.entity_name,
        suggested_description=ko,
        suggested_description_en=en,
        confidence=confidence,
        generation_method="rule_based",
    )

    return {"success": True, "data": result.model_dump()}
