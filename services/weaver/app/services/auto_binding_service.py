"""자동 데이터소스 바인딩 서비스 -- 2단계 매칭 전략.

KAIR의 data_source_linker.py를 참조하여 Axiom Weaver 패턴으로 이식.

2단계 전략:
  Phase 1: 이름 기반 빠른 매칭 (LLM 미사용) -- 테이블/컬럼명 직접 비교
  Phase 2: 시맨틱 매칭 (LLM 사용) -- 의미적 유사도 기반 바인딩 (추후 확장)

기능:
  - 온톨로지 엔티티를 실제 DB 테이블/컬럼에 바인딩
  - FQN (Fully Qualified Name) 생성: datasource.schema.table
  - 한국어 <-> 영어 용어 매핑 지원
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("weaver.auto_binding")


# ── 한국어 <-> 영어 도메인 용어 매핑 (수처리/제조 도메인) ──────────

KO_EN_VOCABULARY: dict[str, list[str]] = {
    "탁도": ["turbidity", "ntu"],
    "잔류염소": ["residual_chlorine", "chlorine", "cl"],
    "수온": ["water_temperature", "temp", "temperature"],
    "pH": ["ph", "ph_level"],
    "유량": ["flow_rate", "flow", "volume"],
    "압력": ["pressure", "psi"],
    "전력": ["power", "electricity", "kwh"],
    "가동률": ["operation_rate", "utilization", "availability"],
    "생산량": ["production", "output", "throughput"],
    "불량률": ["defect_rate", "reject_rate", "quality"],
    "재고": ["inventory", "stock"],
    "매출": ["sales", "revenue"],
    "비용": ["cost", "expense"],
    "고객": ["customer", "client"],
    "주문": ["order", "purchase_order"],
}


@dataclass
class BindingCandidate:
    """바인딩 후보 -- 하나의 엔티티와 매칭된 테이블/컬럼 정보."""

    entity_name: str           # 온톨로지 엔티티 이름
    table_name: str            # 매칭된 테이블
    column_name: str = ""      # 매칭된 컬럼 (있으면)
    datasource: str = ""       # 데이터소스 이름
    schema_name: str = "public"
    fqn: str = ""              # Fully Qualified Name (datasource.schema.table)
    match_method: str = ""     # exact, fuzzy, vocabulary, column_match
    confidence: float = 0.0    # 0.0 ~ 1.0


@dataclass
class BindingResult:
    """바인딩 결과 -- 엔티티별 후보 목록과 최종 상태."""

    entity_name: str
    candidates: list[BindingCandidate] = field(default_factory=list)
    best_match: BindingCandidate | None = None
    status: str = "unbound"  # bound, partial, unbound


# ── Phase 1: 이름 기반 빠른 매칭 ───────────────────────────────────

def _normalize_name(name: str) -> str:
    """이름을 정규화한다 (소문자, 언더스코어 통일, 공백 제거)."""
    return name.lower().replace(" ", "_").replace("-", "_").strip("_")


def _ko_to_en_candidates(korean_name: str) -> list[str]:
    """한국어 이름을 영어 후보 목록으로 변환한다."""
    candidates: list[str] = []
    normalized = _normalize_name(korean_name)

    for ko, en_list in KO_EN_VOCABULARY.items():
        if ko in korean_name or _normalize_name(ko) in normalized:
            candidates.extend(en_list)

    return candidates


def phase1_name_matching(
    entity_name: str,
    available_tables: list[dict[str, Any]],
    datasource: str = "",
) -> list[BindingCandidate]:
    """이름 기반 빠른 매칭 -- LLM 미사용.

    Args:
        entity_name: 온톨로지 엔티티 이름
        available_tables: [{"name": str, "schema": str, "columns": [str]}]
        datasource: 데이터소스 이름

    Returns:
        매칭된 후보 리스트 (confidence 내림차순)
    """
    candidates: list[BindingCandidate] = []
    norm_entity = _normalize_name(entity_name)
    en_alternatives = _ko_to_en_candidates(entity_name)

    for table in available_tables:
        table_name = table.get("name", "")
        schema = table.get("schema", "public")
        norm_table = _normalize_name(table_name)
        columns = table.get("columns", [])

        # 1) 정확 매칭 -- 엔티티명과 테이블명이 완전히 일치
        if norm_entity == norm_table:
            candidates.append(BindingCandidate(
                entity_name=entity_name, table_name=table_name,
                datasource=datasource, schema_name=schema,
                fqn=f"{datasource}.{schema}.{table_name}",
                match_method="exact", confidence=1.0,
            ))
            continue

        # 2) 부분 매칭 -- 테이블명에 엔티티명이 포함되거나 역방향
        if norm_entity in norm_table or norm_table in norm_entity:
            candidates.append(BindingCandidate(
                entity_name=entity_name, table_name=table_name,
                datasource=datasource, schema_name=schema,
                fqn=f"{datasource}.{schema}.{table_name}",
                match_method="fuzzy", confidence=0.7,
            ))
            continue

        # 3) 한국어 -> 영어 변환 매칭 -- 도메인 용어 사전 기반
        matched_via_vocab = False
        for en_name in en_alternatives:
            if en_name in norm_table or norm_table in en_name:
                candidates.append(BindingCandidate(
                    entity_name=entity_name, table_name=table_name,
                    datasource=datasource, schema_name=schema,
                    fqn=f"{datasource}.{schema}.{table_name}",
                    match_method="vocabulary", confidence=0.6,
                ))
                matched_via_vocab = True
                break
        if matched_via_vocab:
            continue

        # 4) 컬럼 레벨 매칭 -- 테이블의 컬럼명에서 엔티티명 탐색
        for col in columns:
            norm_col = _normalize_name(str(col))
            if norm_entity == norm_col or norm_entity in norm_col:
                candidates.append(BindingCandidate(
                    entity_name=entity_name, table_name=table_name,
                    column_name=str(col), datasource=datasource, schema_name=schema,
                    fqn=f"{datasource}.{schema}.{table_name}.{col}",
                    match_method="column_match", confidence=0.5,
                ))

    # confidence 내림차순 정렬
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates


# ── Phase 2: LLM 시맨틱 매칭 ──────────────────────────────────────


async def phase2_semantic_matching(
    entity_name: str,
    entity_description: str,
    available_tables: list[dict[str, Any]],
    datasource: str = "",
) -> list[BindingCandidate]:
    """Phase 2: LLM 시맨틱 매칭 — Phase 1에서 매칭되지 않은 엔티티를 LLM으로 바인딩한다.

    LLM에게 엔티티 설명과 테이블 목록을 제공하고,
    가장 적합한 테이블을 추천받는다.

    gpt-4o-mini를 사용하여 비용을 최소화하면서도
    높은 정확도의 시맨틱 매칭을 수행한다.

    Args:
        entity_name: 온톨로지 엔티티 이름
        entity_description: 엔티티 설명 (비즈니스 컨텍스트)
        available_tables: 바인딩 후보 테이블 목록
        datasource: 데이터소스 이름

    Returns:
        매칭된 후보 리스트 (보통 0~1개)
    """
    # openai가 없으면 빈 결과 반환 (선택적 의존성)
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.debug("openai_not_installed — Phase 2 시맨틱 매칭 비활성화")
        return []

    import os

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.debug("openai_api_key_missing — Phase 2 시맨틱 매칭 비활성화")
        return []

    # 테이블 목록을 LLM이 이해할 수 있는 텍스트로 변환
    table_list = "\n".join(
        f"- {t.get('name', '')} (schema: {t.get('schema', 'public')}, "
        f"columns: {', '.join(str(c) for c in t.get('columns', [])[:10])})"
        for t in available_tables[:50]  # 토큰 절약: 최대 50개 테이블만 전달
    )

    system_prompt = (
        "You are a data engineer matching business entities to database tables.\n"
        "Given an entity name and description, select the most relevant table from the list.\n"
        'Respond in JSON: {"table_name": "...", "confidence": 0.0-1.0, "reasoning": "..."}\n'
        'If no good match exists, return {"table_name": "", "confidence": 0.0, "reasoning": "No match found"}.'
    )

    user_prompt = (
        f"Entity: {entity_name}\n"
        f"Description: {entity_description or 'N/A'}\n\n"
        f"Available tables:\n{table_list}\n\n"
        f"Which table best matches this entity?"
    )

    try:
        import json as _json

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt[:4000]},  # 입력 길이 제한
            ],
            max_tokens=200,
            temperature=0.1,  # 낮은 temperature로 결정적 응답 유도
        )

        raw = response.choices[0].message.content or ""
        # LLM 응답에서 JSON 파싱 (마크다운 코드블록 제거)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # ```json ... ``` 형식 처리
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

        result = _json.loads(cleaned)
        matched_table = result.get("table_name", "")
        confidence = min(1.0, max(0.0, float(result.get("confidence", 0.0))))

        if matched_table and confidence > 0.3:
            # 매칭된 테이블의 스키마 정보 조회
            table_info = next(
                (t for t in available_tables if t.get("name") == matched_table),
                None,
            )
            schema = table_info.get("schema", "public") if table_info else "public"

            logger.info(
                "phase2_semantic_match: entity=%s -> table=%s (confidence=%.2f)",
                entity_name, matched_table, confidence,
            )

            return [BindingCandidate(
                entity_name=entity_name,
                table_name=matched_table,
                datasource=datasource,
                schema_name=schema,
                fqn=f"{datasource}.{schema}.{matched_table}",
                match_method="semantic",
                confidence=confidence,
            )]
        else:
            logger.debug(
                "phase2_no_match: entity=%s (confidence=%.2f, reason=%s)",
                entity_name, confidence, result.get("reasoning", ""),
            )

    except _json.JSONDecodeError as e:
        logger.warning("phase2_json_parse_error: entity=%s error=%s", entity_name, str(e))
    except Exception as e:
        logger.warning("phase2_semantic_matching_failed: entity=%s error=%s", entity_name, str(e))

    return []


# ── 통합 바인딩 ────────────────────────────────────────────────────

async def auto_bind_entities(
    entities: list[str],
    available_tables: list[dict[str, Any]],
    datasource: str = "",
) -> list[BindingResult]:
    """온톨로지 엔티티를 데이터소스 테이블에 자동 바인딩한다.

    2단계 전략으로 매칭을 수행한다:
      Phase 1: 이름 기반 빠른 매칭 (LLM 미사용) — 정확/부분/어휘/컬럼 매칭
      Phase 2: LLM 시맨틱 매칭 — Phase 1에서 unbound인 엔티티만 대상

    Phase 2는 OpenAI API 키가 있는 경우에만 동작한다.
    """
    results: list[BindingResult] = []

    for entity in entities:
        candidates = phase1_name_matching(entity, available_tables, datasource)

        if candidates:
            result = BindingResult(
                entity_name=entity,
                candidates=candidates,
                best_match=candidates[0],
                status="bound" if candidates[0].confidence >= 0.7 else "partial",
            )
        else:
            result = BindingResult(entity_name=entity, status="unbound")

        results.append(result)

    # Phase 2: LLM 시맨틱 매칭 (Phase 1에서 unbound인 것만 대상)
    for result in results:
        if result.status == "unbound":
            phase2_candidates = await phase2_semantic_matching(
                result.entity_name,
                "",  # 엔티티 설명 — 현재는 빈 값 (추후 온톨로지에서 조회)
                available_tables,
                datasource,
            )
            if phase2_candidates:
                result.candidates = phase2_candidates
                result.best_match = phase2_candidates[0]
                # LLM 매칭은 partial로 표시 (사용자 확인 권장)
                result.status = "partial"

    # 바인딩 결과 요약 로그
    bound = sum(1 for r in results if r.status == "bound")
    partial = sum(1 for r in results if r.status == "partial")
    unbound = sum(1 for r in results if r.status == "unbound")
    logger.info(
        "auto_binding_complete: total=%d bound=%d partial=%d unbound=%d",
        len(entities), bound, partial, unbound,
    )

    return results
