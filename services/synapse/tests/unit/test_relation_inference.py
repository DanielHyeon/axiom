"""관계 추론 엔진 단위 테스트."""
import pytest

from app.services.relation_inference import (
    _rule_based_inference,
    infer_relation,
    infer_relations_batch,
)


# ─── 규칙 기반 추론 테스트 ─────────────────────────────────

class TestRuleBasedInference:
    """레이어 규칙 기반 폴백 로직 테스트."""

    def test_kpi_to_measure(self):
        result = _rule_based_inference(
            {"name": "OEE", "layer": "kpi"},
            {"name": "Availability", "layer": "measure"},
        )
        assert result["relation_type"] == "DERIVED_FROM"
        assert result["confidence"] == 0.7

    def test_measure_to_process(self):
        result = _rule_based_inference(
            {"name": "Cycle Time", "layer": "measure"},
            {"name": "Assembly", "layer": "process"},
        )
        assert result["relation_type"] == "OBSERVED_IN"

    def test_process_to_process(self):
        result = _rule_based_inference(
            {"name": "Assembly", "layer": "process"},
            {"name": "Inspection", "layer": "process"},
        )
        assert result["relation_type"] == "PRECEDES"

    def test_process_to_resource(self):
        result = _rule_based_inference(
            {"name": "Assembly", "layer": "process"},
            {"name": "CNC Machine", "layer": "resource"},
        )
        assert result["relation_type"] == "USES"

    def test_resource_to_process(self):
        result = _rule_based_inference(
            {"name": "CNC Machine", "layer": "resource"},
            {"name": "Assembly", "layer": "process"},
        )
        assert result["relation_type"] == "SUPPORTS"

    def test_driver_to_kpi(self):
        result = _rule_based_inference(
            {"name": "Exchange Rate", "layer": "driver"},
            {"name": "OEE", "layer": "kpi"},
        )
        assert result["relation_type"] == "INFLUENCES"

    def test_driver_to_measure(self):
        result = _rule_based_inference(
            {"name": "Oil Price", "layer": "driver"},
            {"name": "Cost", "layer": "measure"},
        )
        assert result["relation_type"] == "CAUSES"

    def test_unknown_layers_fallback(self):
        """알 수 없는 레이어 조합은 RELATED_TO + 낮은 신뢰도."""
        result = _rule_based_inference(
            {"name": "A", "layer": "resource"},
            {"name": "B", "layer": "kpi"},
        )
        assert result["relation_type"] == "RELATED_TO"
        assert result["confidence"] == 0.3

    def test_missing_layer(self):
        """레이어 정보 없으면 RELATED_TO 폴백."""
        result = _rule_based_inference(
            {"name": "X"},
            {"name": "Y"},
        )
        assert result["relation_type"] == "RELATED_TO"


# ─── infer_relation 테스트 (LLM 미사용) ────────────────────

@pytest.mark.asyncio
async def test_infer_relation_without_api_key():
    """OPENAI_API_KEY 비어 있으면 규칙 기반 폴백 사용."""
    result = await infer_relation(
        {"name": "OEE", "layer": "kpi", "description": "전체 설비 효율"},
        {"name": "Availability", "layer": "measure", "description": "가동률"},
    )
    assert result["relation_type"] == "DERIVED_FROM"
    assert result["confidence"] == 0.7
    assert result["direction"] == "source_to_target"


# ─── infer_relations_batch 테스트 ──────────────────────────

@pytest.mark.asyncio
async def test_batch_inference():
    """배치 추론 — 3개 엔티티 → 최대 3쌍 비교."""
    entities = [
        {"name": "OEE", "layer": "kpi", "description": ""},
        {"name": "Availability", "layer": "measure", "description": ""},
        {"name": "Assembly", "layer": "process", "description": ""},
    ]
    results = await infer_relations_batch(entities, min_confidence=0.5)
    # kpi→measure(0.7), kpi→process(0.7), measure→process(0.7) 모두 >= 0.5
    assert len(results) == 3


@pytest.mark.asyncio
async def test_batch_inference_filters_low_confidence():
    """min_confidence 이상만 반환."""
    entities = [
        {"name": "Sensor", "layer": "resource", "description": ""},
        {"name": "OEE", "layer": "kpi", "description": ""},
    ]
    # resource→kpi는 RELATED_TO(0.3) → min_confidence=0.5이면 제외
    results = await infer_relations_batch(entities, min_confidence=0.5)
    assert len(results) == 0
