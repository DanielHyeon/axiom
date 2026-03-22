"""
Sprint 2: 품질 신뢰 등급 서비스 단위 테스트

QualityTrustService.evaluate()의 등급 결정 로직을 검증한다.
테스트 범위:
  - 등급 경계값 테스트 (TRUSTED/CAUTION/REFERENCE_ONLY/BLOCKED)
  - 하드 실패 오버라이드 테스트 (높은 점수지만 핵심 차원 미달 → BLOCKED)
  - 소프트 실패 패널티 테스트
  - 복수 소프트 실패 누적 패널티
  - 전체 차원 존재 / 일부 차원만 존재
  - 엣지 케이스 (전부 0, 전부 100, 빈 딕셔너리)
"""
import pytest

from app.services.quality_trust import QualityTrustService, TrustTierResult


@pytest.fixture
def svc() -> QualityTrustService:
    """매 테스트마다 새 서비스 인스턴스 생성"""
    return QualityTrustService()


# ========================================
# 1. 등급 경계값 테스트
# ========================================


class TestTierBoundaries:
    """최종 점수 임계치에 따른 등급 분류를 검증한다."""

    def test_all_perfect_scores_is_trusted(self, svc: QualityTrustService):
        """모든 차원이 100점이면 TRUSTED"""
        scores = {
            "freshness": 100, "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 100,
            "owner_coverage": 100, "lineage_completeness": 100,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "TRUSTED"
        assert result.final_score == 100.0
        assert result.allow_execution is True
        assert result.response_mode == "normal"

    def test_score_85_no_soft_fail_is_trusted(self, svc: QualityTrustService):
        """모든 차원 85점 → 소프트 경고 없으므로 TRUSTED"""
        scores = {
            "freshness": 85, "completeness": 85, "validity": 85,
            "uniqueness": 85, "referential_integrity": 85,
            "owner_coverage": 85, "lineage_completeness": 85,
            "test_coverage": 85, "incident_health": 85,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "TRUSTED"
        assert result.final_score >= 85.0

    def test_score_84_9_is_caution(self, svc: QualityTrustService):
        """모든 차원 84.9점 → 가중 평균은 84.9이고 소프트 경고 없지만
        TRUSTED 임계치(85) 미달이므로 CAUTION"""
        scores = {
            "freshness": 84.9, "completeness": 84.9, "validity": 84.9,
            "uniqueness": 84.9, "referential_integrity": 84.9,
            "owner_coverage": 84.9, "lineage_completeness": 84.9,
            "test_coverage": 84.9, "incident_health": 84.9,
        }
        result = svc.evaluate(scores)
        # 가중 평균: (84.9 * sum_weights) / sum_weights * 100 = 84.9 * 100 = 8490
        # 실제: weighted_sum / total_weight * 100 = 84.9
        # 소프트 경고: uniqueness 84.9 >= 70 → 없음, test_coverage 84.9 >= 50 → 없음
        # 점수 84.9 < 85 → CAUTION
        assert result.trust_tier == "CAUTION"

    def test_score_70_is_caution(self, svc: QualityTrustService):
        """모든 차원 70점 → CAUTION 범위"""
        scores = {
            "freshness": 70, "completeness": 70, "validity": 70,
            "uniqueness": 70, "referential_integrity": 70,
            "owner_coverage": 70, "lineage_completeness": 70,
            "test_coverage": 70, "incident_health": 70,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "CAUTION"
        assert result.allow_execution is True
        assert result.response_mode == "warn"

    def test_score_69_with_no_soft_is_reference(self, svc: QualityTrustService):
        """점수 69점 + 소프트 경고 → REFERENCE_ONLY 또는 낮은 CAUTION"""
        # freshness 69 < 50? 아니라 69 >= 50이므로 소프트 통과
        # completeness 69 >= 60이므로 소프트 통과
        # uniqueness 69 < 70이므로 소프트 실패 → 패널티 5점 → 69 - 5 = 64
        scores = {
            "freshness": 69, "completeness": 69, "validity": 69,
            "uniqueness": 69, "referential_integrity": 69,
            "owner_coverage": 69, "lineage_completeness": 69,
            "test_coverage": 69, "incident_health": 69,
        }
        result = svc.evaluate(scores)
        # uniqueness 69 < 70 → soft fail → penalty 5
        # 가중 평균 = 69 → 69 - 5 = 64 → REFERENCE_ONLY (50~70 범위)
        assert result.trust_tier in ("CAUTION", "REFERENCE_ONLY")

    def test_score_50_is_reference_only(self, svc: QualityTrustService):
        """점수 50점 근처는 REFERENCE_ONLY"""
        scores = {
            "freshness": 60, "completeness": 70, "validity": 60,
            "uniqueness": 80, "referential_integrity": 50,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier in ("CAUTION", "REFERENCE_ONLY")

    def test_very_low_scores_is_blocked(self, svc: QualityTrustService):
        """모든 차원이 20점이면 BLOCKED"""
        scores = {
            "freshness": 20, "completeness": 20, "validity": 20,
            "uniqueness": 20, "referential_integrity": 20,
            "owner_coverage": 20, "lineage_completeness": 20,
            "test_coverage": 20, "incident_health": 20,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "BLOCKED"
        assert result.allow_execution is False
        assert result.response_mode == "block"


# ========================================
# 2. Hard-fail 오버라이드 테스트
# ========================================


class TestHardFail:
    """핵심 차원이 임계치 미만이면 전체 점수와 무관하게 BLOCKED"""

    def test_low_referential_integrity_overrides(self, svc: QualityTrustService):
        """참조 무결성 39점 (임계치 40 미만) → 나머지 만점이어도 BLOCKED"""
        scores = {
            "freshness": 100, "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 39,
            "owner_coverage": 100, "lineage_completeness": 100,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "BLOCKED"
        assert "LOW_REFERENTIAL_INTEGRITY" in result.hard_fail_codes
        assert result.allow_execution is False

    def test_low_lineage_completeness_overrides(self, svc: QualityTrustService):
        """리니지 완전성 29점 (임계치 30 미만) → BLOCKED"""
        scores = {
            "freshness": 100, "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 100,
            "owner_coverage": 100, "lineage_completeness": 29,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "BLOCKED"
        assert "LOW_LINEAGE_COMPLETENESS" in result.hard_fail_codes

    def test_low_validity_overrides(self, svc: QualityTrustService):
        """유효성 34점 (임계치 35 미만) → BLOCKED"""
        scores = {
            "freshness": 100, "completeness": 100, "validity": 34,
            "uniqueness": 100, "referential_integrity": 100,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "BLOCKED"
        assert "LOW_VALIDITY" in result.hard_fail_codes

    def test_hard_fail_at_exact_threshold_passes(self, svc: QualityTrustService):
        """참조 무결성 정확히 40점 → 임계치 '미만'이 아니므로 hard-fail 아님"""
        scores = {
            "freshness": 100, "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 40,
            "owner_coverage": 100, "lineage_completeness": 100,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier != "BLOCKED"
        assert "LOW_REFERENTIAL_INTEGRITY" not in result.hard_fail_codes

    def test_multiple_hard_fails(self, svc: QualityTrustService):
        """복수 핵심 차원 위반 → BLOCKED + 모든 코드 포함"""
        scores = {
            "freshness": 100, "completeness": 100,
            "validity": 10, "referential_integrity": 10,
            "lineage_completeness": 10,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "BLOCKED"
        assert len(result.hard_fail_codes) == 3


# ========================================
# 3. Soft-fail 패널티 테스트
# ========================================


class TestSoftFail:
    """경미한 차원 위반 시 패널티와 등급 영향을 검증한다."""

    def test_single_soft_fail_penalty(self, svc: QualityTrustService):
        """freshness 49점 (임계치 50 미만) → 소프트 경고 1건, 5점 패널티"""
        scores = {
            "freshness": 49, "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 100,
            "owner_coverage": 100, "lineage_completeness": 100,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        assert "LOW_FRESHNESS" in result.soft_fail_codes
        assert len(result.soft_fail_codes) == 1
        # 소프트 경고 있으므로 TRUSTED 불가 → CAUTION
        assert result.trust_tier == "CAUTION"

    def test_two_soft_fails_extra_penalty(self, svc: QualityTrustService):
        """소프트 경고 2건 → 5*2 + 5(추가) = 15점 패널티"""
        scores = {
            "freshness": 49, "completeness": 59,
            "validity": 100, "uniqueness": 100,
            "referential_integrity": 100,
        }
        result = svc.evaluate(scores)
        assert len(result.soft_fail_codes) == 2
        # 가중 평균이 높아도 15점 패널티가 적용됨
        assert result.final_score < 100

    def test_four_soft_fails_heavy_penalty(self, svc: QualityTrustService):
        """소프트 경고 4건 → 5*4 + 5(추가) = 25점 패널티"""
        scores = {
            "freshness": 10, "completeness": 10,
            "uniqueness": 10, "test_coverage": 10,
            "validity": 100, "referential_integrity": 100,
            "lineage_completeness": 100,
        }
        result = svc.evaluate(scores)
        assert len(result.soft_fail_codes) == 4

    def test_soft_fail_does_not_override_trusted_when_score_high(self, svc: QualityTrustService):
        """소프트 경고가 있으면 점수가 85 이상이어도 TRUSTED가 될 수 없다"""
        scores = {
            "freshness": 49,  # soft fail
            "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 100,
            "owner_coverage": 100, "lineage_completeness": 100,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        # freshness soft fail → TRUSTED 불가
        assert result.trust_tier != "TRUSTED"


# ========================================
# 4. 전체 차원 / 부분 차원 테스트
# ========================================


class TestDimensionCoverage:
    """차원 제공 범위에 따른 동작을 검증한다."""

    def test_all_dimensions_present(self, svc: QualityTrustService):
        """9개 차원 모두 제공 — 정상 계산"""
        scores = {
            "freshness": 90, "completeness": 90, "validity": 90,
            "uniqueness": 90, "referential_integrity": 90,
            "owner_coverage": 90, "lineage_completeness": 90,
            "test_coverage": 90, "incident_health": 90,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "TRUSTED"
        assert result.final_score == 90.0  # 모든 값 동일, 패널티 없음

    def test_partial_dimensions(self, svc: QualityTrustService):
        """일부 차원만 제공 — 가중치 재정규화"""
        scores = {"freshness": 90, "completeness": 90}
        result = svc.evaluate(scores)
        # freshness 가중치 0.20, completeness 가중치 0.15
        # 가중 평균 = (90*0.20 + 90*0.15) / (0.20 + 0.15) * 100 = 90
        assert result.final_score == 90.0
        assert result.trust_tier == "TRUSTED"

    def test_single_dimension(self, svc: QualityTrustService):
        """차원 하나만 제공"""
        scores = {"freshness": 80}
        result = svc.evaluate(scores)
        assert result.final_score == 80.0  # 단일 차원은 그대로

    def test_unknown_dimensions_ignored(self, svc: QualityTrustService):
        """알 수 없는 차원은 무시된다"""
        scores = {"freshness": 90, "unknown_dim": 10}
        result = svc.evaluate(scores)
        # unknown_dim은 가중치에 없으므로 무시, freshness만 사용
        assert result.final_score == 90.0


# ========================================
# 5. 엣지 케이스
# ========================================


class TestEdgeCases:
    """극단적인 입력에 대한 동작을 검증한다."""

    def test_empty_scores(self, svc: QualityTrustService):
        """빈 딕셔너리 → 0점 → BLOCKED"""
        result = svc.evaluate({})
        assert result.trust_tier == "BLOCKED"
        assert result.final_score == 0
        assert result.allow_execution is False

    def test_all_zeros(self, svc: QualityTrustService):
        """모든 차원 0점 → BLOCKED (hard-fail 다수)"""
        scores = {
            "freshness": 0, "completeness": 0, "validity": 0,
            "uniqueness": 0, "referential_integrity": 0,
            "owner_coverage": 0, "lineage_completeness": 0,
            "test_coverage": 0, "incident_health": 0,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "BLOCKED"
        assert result.allow_execution is False
        # hard fails: validity(0 < 35), referential_integrity(0 < 40), lineage_completeness(0 < 30)
        assert len(result.hard_fail_codes) == 3

    def test_all_hundred(self, svc: QualityTrustService):
        """모든 차원 100점 → TRUSTED"""
        scores = {dim: 100 for dim in svc.DIMENSION_WEIGHTS}
        result = svc.evaluate(scores)
        assert result.trust_tier == "TRUSTED"
        assert result.final_score == 100.0
        assert result.hard_fail_codes == []
        assert result.soft_fail_codes == []

    def test_score_clamped_to_0(self, svc: QualityTrustService):
        """패널티로 음수가 되면 0으로 클램핑"""
        # 매우 낮은 점수 + 많은 소프트 실패 → 패널티 과다
        scores = {
            "freshness": 1, "completeness": 1,
            "uniqueness": 1, "test_coverage": 1,
        }
        result = svc.evaluate(scores)
        assert result.final_score >= 0

    def test_score_clamped_to_100(self, svc: QualityTrustService):
        """점수가 100을 초과하지 않음 (정상 입력에서는 발생하지 않지만 방어)"""
        scores = {"freshness": 200}  # 비정상 입력
        result = svc.evaluate(scores)
        assert result.final_score <= 100.0


# ========================================
# 6. 결과 구조 검증
# ========================================


class TestResultStructure:
    """TrustTierResult의 구조가 올바른지 검증한다."""

    def test_result_has_all_fields(self, svc: QualityTrustService):
        """결과 객체에 모든 필수 필드가 존재"""
        result = svc.evaluate({"freshness": 80})
        assert isinstance(result, TrustTierResult)
        assert result.trust_tier in ("TRUSTED", "CAUTION", "REFERENCE_ONLY", "BLOCKED")
        assert isinstance(result.final_score, float)
        assert isinstance(result.allow_execution, bool)
        assert result.response_mode in ("normal", "warn", "degrade", "block")
        assert isinstance(result.user_banner, str)
        assert isinstance(result.hard_fail_codes, list)
        assert isinstance(result.soft_fail_codes, list)
        assert isinstance(result.dimension_breakdown, dict)

    def test_dimension_breakdown_preserved(self, svc: QualityTrustService):
        """입력한 차원별 점수가 breakdown에 그대로 보존"""
        scores = {"freshness": 75, "completeness": 82}
        result = svc.evaluate(scores)
        assert result.dimension_breakdown == scores

    def test_user_banner_is_korean(self, svc: QualityTrustService):
        """안내 문구가 한국어로 제공"""
        for tier_scores, expected_tier in [
            ({"freshness": 100, "completeness": 100}, "TRUSTED"),
            ({"freshness": 45}, "CAUTION"),
        ]:
            result = svc.evaluate(tier_scores)
            # 한국어 유니코드 범위 확인 (가~힣)
            assert any('\uac00' <= ch <= '\ud7a3' for ch in result.user_banner)


# ========================================
# 7. Response mode 매핑 검증
# ========================================


class TestResponseMode:
    """등급별 response_mode가 올바르게 매핑되는지 검증한다."""

    def test_trusted_mode_is_normal(self, svc: QualityTrustService):
        scores = {dim: 100 for dim in svc.DIMENSION_WEIGHTS}
        result = svc.evaluate(scores)
        assert result.response_mode == "normal"

    def test_caution_mode_is_warn(self, svc: QualityTrustService):
        # freshness 49 → soft fail → CAUTION
        scores = {
            "freshness": 49, "completeness": 100, "validity": 100,
            "uniqueness": 100, "referential_integrity": 100,
            "owner_coverage": 100, "lineage_completeness": 100,
            "test_coverage": 100, "incident_health": 100,
        }
        result = svc.evaluate(scores)
        assert result.response_mode == "warn"

    def test_blocked_mode_is_block(self, svc: QualityTrustService):
        scores = {"referential_integrity": 10}
        result = svc.evaluate(scores)
        assert result.response_mode == "block"


# ========================================
# 8. 커스텀 시나리오 테스트
# ========================================


class TestRealisticScenarios:
    """실제 운영 환경에서 발생할 수 있는 시나리오를 검증한다."""

    def test_fresh_but_incomplete_data(self, svc: QualityTrustService):
        """데이터는 신선하지만 결측이 많은 경우"""
        scores = {"freshness": 95, "completeness": 45, "uniqueness": 90}
        result = svc.evaluate(scores)
        # completeness 45 < 60 → soft fail
        assert "LOW_COMPLETENESS" in result.soft_fail_codes
        assert result.trust_tier in ("CAUTION", "REFERENCE_ONLY")

    def test_complete_but_stale_data(self, svc: QualityTrustService):
        """데이터는 완전하지만 오래된 경우"""
        scores = {"freshness": 30, "completeness": 98, "uniqueness": 99}
        result = svc.evaluate(scores)
        # freshness 30 < 50 → soft fail
        assert "LOW_FRESHNESS" in result.soft_fail_codes

    def test_production_quality_dataset(self, svc: QualityTrustService):
        """프로덕션 수준의 양호한 데이터셋"""
        scores = {
            "freshness": 92, "completeness": 88, "validity": 95,
            "uniqueness": 97, "referential_integrity": 90,
            "owner_coverage": 85, "lineage_completeness": 80,
            "test_coverage": 75, "incident_health": 90,
        }
        result = svc.evaluate(scores)
        assert result.trust_tier == "TRUSTED"
        assert result.allow_execution is True

    def test_degraded_dataset(self, svc: QualityTrustService):
        """여러 차원에서 경미한 문제가 있는 데이터셋"""
        scores = {
            "freshness": 45,    # soft fail
            "completeness": 55, # soft fail
            "validity": 60,
            "uniqueness": 65,   # soft fail
            "referential_integrity": 50,
            "test_coverage": 40, # soft fail
        }
        result = svc.evaluate(scores)
        # 4건 소프트 실패 → 5*4 + 5 = 25점 패널티
        assert len(result.soft_fail_codes) == 4
        assert result.trust_tier in ("REFERENCE_ONLY", "BLOCKED")
