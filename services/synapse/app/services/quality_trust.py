"""
Sprint 2: 품질 신뢰 등급 결정 서비스

시멘틱 계약의 품질 점수(freshness, completeness, uniqueness 등)를
기반으로 4단계 신뢰 등급을 결정한다.

등급 체계:
  TRUSTED        — 모든 품질 기준 충족, 정상 사용 가능
  CAUTION        — 일부 소프트 경고, 결과 사용 시 주의 필요
  REFERENCE_ONLY — 품질 미달, 참고용으로만 사용
  BLOCKED        — 핵심 품질 기준 미충족, 결과 제공 불가
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrustTierResult:
    """품질 신뢰 등급 평가 결과

    Attributes:
        trust_tier: 4단계 등급 (TRUSTED / CAUTION / REFERENCE_ONLY / BLOCKED)
        final_score: 가중 평균 + 패널티가 반영된 최종 점수 (0~100)
        allow_execution: 쿼리 실행 허용 여부 (BLOCKED이면 False)
        response_mode: 응답 모드 (normal / warn / degrade / block)
        user_banner: 사용자에게 보여줄 한국어 안내 문구
        hard_fail_codes: 핵심 품질 위반 코드 목록
        soft_fail_codes: 경미한 품질 경고 코드 목록
        dimension_breakdown: 차원별 원본 점수 (디버깅/UI 표시용)
    """

    trust_tier: str
    final_score: float
    allow_execution: bool
    response_mode: str
    user_banner: str
    hard_fail_codes: list[str] = field(default_factory=list)
    soft_fail_codes: list[str] = field(default_factory=list)
    dimension_breakdown: dict[str, float] = field(default_factory=dict)


class QualityTrustService:
    """품질 점수를 기반으로 신뢰 등급을 결정하는 서비스

    사용법:
        svc = QualityTrustService()
        result = svc.evaluate({"freshness": 90, "completeness": 85, "uniqueness": 95})
        # result.trust_tier → "TRUSTED"
    """

    # --- 등급별 최소 점수 임계치 ---
    # 점수가 이 값 이상이면 해당 등급에 해당한다
    TIER_THRESHOLDS = {
        "TRUSTED": 85,          # 85점 이상이고 소프트 경고 없으면 신뢰
        "CAUTION": 70,          # 70점 이상이면 주의
        "REFERENCE_ONLY": 50,   # 50점 이상이면 참고용
        # 50점 미만이면 BLOCKED
    }

    # --- 하드 실패 임계치 ---
    # 이 차원의 점수가 임계치 미만이면 무조건 BLOCKED
    HARD_FAIL_THRESHOLDS = {
        "referential_integrity": 40,  # 참조 무결성이 40 미만이면 위험
        "lineage_completeness": 30,   # 리니지 추적이 30 미만이면 출처 불명
        "validity": 35,               # 유효성이 35 미만이면 데이터 신뢰 불가
    }

    # --- 소프트 실패 임계치 ---
    # 이 차원의 점수가 임계치 미만이면 경고 + 패널티 부과
    SOFT_FAIL_THRESHOLDS = {
        "freshness": 50,      # 신선도 50 미만이면 오래된 데이터 경고
        "completeness": 60,   # 완전성 60 미만이면 결측 데이터 경고
        "uniqueness": 70,     # 고유성 70 미만이면 중복 데이터 경고
        "test_coverage": 50,  # 테스트 커버리지 50 미만이면 검증 부족 경고
    }

    # --- 가중치 설정 ---
    # 각 차원이 최종 점수에 기여하는 비율
    DIMENSION_WEIGHTS = {
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

    # --- 등급별 응답 모드 + 사용자 안내 문구 ---
    _TIER_CONFIG: dict[str, tuple[str, str]] = {
        "TRUSTED": (
            "normal",
            "현재 승인된 시맨틱 계약 기준으로 결과를 제공합니다.",
        ),
        "CAUTION": (
            "warn",
            "결과는 제공되지만 일부 품질 신호가 낮아 해석에 주의가 필요합니다.",
        ),
        "REFERENCE_ONLY": (
            "degrade",
            "이 결과는 참고용입니다. 일부 품질 지표가 기준 미만이므로 업무 의사결정에는 추가 검증이 필요합니다.",
        ),
        "BLOCKED": (
            "block",
            "현재 이 시맨틱 계약의 품질 기준을 충족하지 않아 결과 제공이 제한됩니다.",
        ),
    }

    def evaluate(self, dimension_scores: dict[str, float]) -> TrustTierResult:
        """차원별 점수를 받아 신뢰 등급을 결정한다.

        Args:
            dimension_scores: 차원 이름 → 점수(0~100) 딕셔너리
                예: {"freshness": 90, "completeness": 85, "uniqueness": 95}

        Returns:
            TrustTierResult: 등급 평가 결과
        """
        # 1단계: 핵심 차원(hard-fail) 검사
        # — 이 차원이 임계치 미만이면 나머지 점수와 무관하게 BLOCKED
        hard_fails: list[str] = []
        for dim, threshold in self.HARD_FAIL_THRESHOLDS.items():
            score = dimension_scores.get(dim)
            if score is not None and score < threshold:
                hard_fails.append(f"LOW_{dim.upper()}")

        # 2단계: 경미한 차원(soft-fail) 검사
        # — 경고 코드를 수집하고, 개수에 비례하여 패널티를 부과한다
        soft_fails: list[str] = []
        for dim, threshold in self.SOFT_FAIL_THRESHOLDS.items():
            score = dimension_scores.get(dim)
            if score is not None and score < threshold:
                soft_fails.append(f"LOW_{dim.upper()}")

        # 3단계: 가중 평균 계산 (제공된 차원만 사용)
        # — 점수가 없는 차원은 무시하고, 있는 차원의 가중치를 재정규화한다
        total_weight = 0.0
        weighted_sum = 0.0
        for dim, weight in self.DIMENSION_WEIGHTS.items():
            score = dimension_scores.get(dim)
            if score is not None:
                weighted_sum += score * weight
                total_weight += weight

        # 차원이 하나도 없으면 0점
        # 점수가 0~100 범위이므로 가중 평균도 0~100 범위
        final_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0

        # 4단계: 소프트 실패 패널티 적용
        # — 소프트 경고 1건당 5점 감점, 2건 이상이면 추가 5점 감점
        penalty = len(soft_fails) * 5 + (5 if len(soft_fails) >= 2 else 0)
        final_score = max(0.0, min(100.0, final_score - penalty))

        # 5단계: 등급 결정
        if hard_fails:
            # 핵심 위반이 있으면 무조건 BLOCKED
            tier = "BLOCKED"
        elif final_score >= self.TIER_THRESHOLDS["TRUSTED"] and not soft_fails:
            # 점수 충분 + 소프트 경고 없음 → TRUSTED
            tier = "TRUSTED"
        elif final_score >= self.TIER_THRESHOLDS["CAUTION"]:
            tier = "CAUTION"
        elif final_score >= self.TIER_THRESHOLDS["REFERENCE_ONLY"]:
            tier = "REFERENCE_ONLY"
        else:
            tier = "BLOCKED"

        # 6단계: 응답 모드 + 안내 문구 결정
        response_mode, banner = self._TIER_CONFIG[tier]

        return TrustTierResult(
            trust_tier=tier,
            final_score=round(final_score, 2),
            allow_execution=(tier != "BLOCKED"),
            response_mode=response_mode,
            user_banner=banner,
            hard_fail_codes=hard_fails,
            soft_fail_codes=soft_fails,
            dimension_breakdown=dict(dimension_scores),
        )


# 모듈 레벨 싱글턴 (다른 서비스에서 import하여 사용)
quality_trust_service = QualityTrustService()
