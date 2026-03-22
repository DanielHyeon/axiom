"""
Sprint 2: 품질 신뢰 등급 게이트

시멘틱 컨텍스트의 품질 정보를 분석하여 4단계 신뢰 등급을 결정한다.

두 가지 평가 경로를 지원한다:
1. 구조화된 차원별 점수가 있으면 → 정확한 가중 평균 계산 (우선)
2. 텍스트 경고만 있으면 → 키워드 기반 감점 추정 (폴백)
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("oracle.quality_gate")

# --- 등급별 임계치 ---
_TIER_THRESHOLDS = {
    "TRUSTED": 85,
    "CAUTION": 70,
    "REFERENCE_ONLY": 50,
}

# --- 9차원 가중치 (계획서 §11.2 일치) ---
_DIMENSION_WEIGHTS = {
    "freshness": 0.20,
    "completeness": 0.15,
    "validity": 0.10,
    "uniqueness": 0.10,
    "referential_integrity": 0.10,
    "owner_coverage": 0.10,
    "lineage_completeness": 0.10,
    "test_coverage": 0.05,
    "incident_health": 0.10,
}

# --- Hard-fail 차원별 임계치 ---
_HARD_FAIL_THRESHOLDS = {
    "referential_integrity": 40,
    "lineage_completeness": 30,
    "validity": 35,
}

# --- Soft-fail 차원별 임계치 ---
_SOFT_FAIL_THRESHOLDS = {
    "freshness": 50,
    "completeness": 60,
    "uniqueness": 70,
    "test_coverage": 50,
}

# --- 텍스트 경고 키워드 → 차원 매핑 + 감점 (폴백용) ---
_WARNING_PATTERNS: list[tuple[str, str, float]] = [
    (r"freshness|신선도|오래된|stale|outdated", "freshness", 25),
    (r"completeness|완전성|결측|missing|null|누락", "completeness", 20),
    (r"uniqueness|고유성|중복|duplicate", "uniqueness", 15),
    (r"referential|참조\s*무결|integrity|무결성", "referential_integrity", 35),
    (r"lineage|리니지|출처", "lineage_completeness", 30),
    (r"validity|유효성|invalid|범위\s*초과", "validity", 25),
    (r"test|테스트|coverage|커버리지", "test_coverage", 10),
    (r"owner|소유자|담당자", "owner_coverage", 10),
    (r"incident|장애|사고", "incident_health", 15),
]

# --- 등급별 응답 설정 ---
_TIER_CONFIG = {
    "TRUSTED": {
        "response_mode": "normal",
        "user_banner": "현재 승인된 시맨틱 계약 기준으로 결과를 제공합니다.",
        "allow_execution": True,
    },
    "CAUTION": {
        "response_mode": "warn",
        "user_banner": "결과는 제공되지만 일부 품질 신호가 낮아 해석에 주의가 필요합니다.",
        "allow_execution": True,
    },
    "REFERENCE_ONLY": {
        "response_mode": "degrade",
        "user_banner": "이 결과는 참고용입니다. 일부 품질 지표가 기준 미만이므로 업무 의사결정에는 추가 검증이 필요합니다.",
        "allow_execution": True,
    },
    "BLOCKED": {
        "response_mode": "block",
        "user_banner": "현재 이 시맨틱 계약의 품질 기준을 충족하지 않아 결과 제공이 제한됩니다.",
        "allow_execution": False,
    },
}


def evaluate_trust_tier(
    quality_warnings: list[str] | None = None,
    dimension_scores: dict[str, float] | None = None,
) -> dict:
    """품질 정보를 분석하여 신뢰 등급을 결정한다.

    두 가지 입력을 지원한다 (구조화 점수 우선):
    1. dimension_scores: {"freshness": 95, "completeness": 80, ...} → 정확한 평가
    2. quality_warnings: ["완전성 85% < 90%", ...] → 텍스트 기반 추정

    Returns:
        dict: 신뢰 등급 정보
            - trust_tier: "TRUSTED" | "CAUTION" | "REFERENCE_ONLY" | "BLOCKED"
            - final_score: 최종 점수 (0~100)
            - allow_execution: 실행 허용 여부
            - response_mode: 응답 모드
            - user_banner: 사용자 안내 문구
            - hard_fail_codes / soft_fail_codes: 위반 코드 목록
    """
    # 입력이 모두 없으면 TRUSTED
    if not quality_warnings and not dimension_scores:
        config = _TIER_CONFIG["TRUSTED"]
        return {
            "trust_tier": "TRUSTED",
            "final_score": 100.0,
            **config,
            "hard_fail_codes": [],
            "soft_fail_codes": [],
        }

    # 구조화된 점수가 있으면 정확한 평가 경로 사용
    if dimension_scores:
        return _evaluate_from_scores(dimension_scores)

    # 텍스트 경고만 있으면 폴백 평가
    return _evaluate_from_warnings(quality_warnings or [])


def _evaluate_from_scores(scores: dict[str, float]) -> dict:
    """구조화된 차원별 점수로 정확한 신뢰 등급을 계산한다."""
    # 1. Hard-fail 검사
    hard_fail_codes: list[str] = []
    for dim, threshold in _HARD_FAIL_THRESHOLDS.items():
        score = scores.get(dim)
        if score is not None and score < threshold:
            hard_fail_codes.append(f"LOW_{dim.upper()}")

    # 2. Soft-fail 검사
    soft_fail_codes: list[str] = []
    for dim, threshold in _SOFT_FAIL_THRESHOLDS.items():
        score = scores.get(dim)
        if score is not None and score < threshold:
            soft_fail_codes.append(f"LOW_{dim.upper()}")

    # 3. 가중 평균 계산 (존재하는 차원만)
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        score = scores.get(dim)
        if score is not None:
            weighted_sum += score * weight
            total_weight += weight

    # 차원 점수가 이미 0~100 범위이므로 가중 평균도 0~100이다 (×100 하지 않음)
    final_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0

    # 4. Penalty 적용
    penalty = len(soft_fail_codes) * 5 + (5 if len(soft_fail_codes) >= 2 else 0)
    final_score = max(0.0, min(100.0, final_score - penalty))

    # 5. 등급 결정
    return _decide_tier(final_score, hard_fail_codes, soft_fail_codes)


def _evaluate_from_warnings(warnings: list[str]) -> dict:
    """텍스트 경고 기반 폴백 평가 (구조화 점수가 없을 때)."""
    # 경고 텍스트에서 차원별 감점 추출
    dimension_penalties: dict[str, float] = {}
    for warning in warnings:
        warning_lower = warning.lower()
        for pattern, dim, penalty in _WARNING_PATTERNS:
            if re.search(pattern, warning_lower):
                dimension_penalties[dim] = max(
                    dimension_penalties.get(dim, 0), penalty
                )

    # 기본 100점에서 감점
    total_penalty = sum(dimension_penalties.values())
    final_score = max(0.0, 100.0 - total_penalty)

    # hard-fail / soft-fail 분류
    hard_fail_codes: list[str] = []
    soft_fail_codes: list[str] = []
    for dim, penalty in dimension_penalties.items():
        code = f"LOW_{dim.upper()}"
        if dim in _HARD_FAIL_THRESHOLDS and penalty >= 25:
            hard_fail_codes.append(code)
        else:
            soft_fail_codes.append(code)

    return _decide_tier(final_score, hard_fail_codes, soft_fail_codes)


def _decide_tier(
    final_score: float,
    hard_fail_codes: list[str],
    soft_fail_codes: list[str],
) -> dict:
    """점수와 위반 코드를 기반으로 최종 등급을 결정한다."""
    if hard_fail_codes:
        tier = "BLOCKED"
    elif final_score >= _TIER_THRESHOLDS["TRUSTED"] and not soft_fail_codes:
        tier = "TRUSTED"
    elif final_score >= _TIER_THRESHOLDS["CAUTION"]:
        tier = "CAUTION"
    elif final_score >= _TIER_THRESHOLDS["REFERENCE_ONLY"]:
        tier = "REFERENCE_ONLY"
    else:
        tier = "BLOCKED"

    config = _TIER_CONFIG[tier]
    return {
        "trust_tier": tier,
        "final_score": round(final_score, 2),
        **config,
        "hard_fail_codes": hard_fail_codes,
        "soft_fail_codes": soft_fail_codes,
    }
