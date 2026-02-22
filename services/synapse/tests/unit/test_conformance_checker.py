import pytest

from app.mining.conformance_checker import check_conformance


def test_conformance_checker_scores_and_diagnostics():
    events = [
        {"case_id": "c1", "activity": "주문 접수", "timestamp": "2024-01-01T09:00:00Z"},
        {"case_id": "c1", "activity": "결제 확인", "timestamp": "2024-01-01T10:00:00Z"},
        {"case_id": "c1", "activity": "출하 지시", "timestamp": "2024-01-01T11:00:00Z"},
        {"case_id": "c2", "activity": "주문 접수", "timestamp": "2024-01-02T09:00:00Z"},
        {"case_id": "c2", "activity": "배송 완료", "timestamp": "2024-01-02T15:00:00Z"},
    ]
    designed = ["주문 접수", "결제 확인", "출하 지시"]

    result = check_conformance(
        events=events,
        designed_activities=designed,
        include_case_diagnostics=True,
        max_diagnostics_cases=10,
    )

    assert result.total_cases == 2
    assert result.conformant_cases == 1
    assert 0.0 <= result.fitness <= 1.0
    assert len(result.case_diagnostics) == 2
    assert "skipped_activities" in result.deviation_statistics


def test_conformance_checker_validates_inputs():
    with pytest.raises(ValueError):
        check_conformance(events=[], designed_activities=["A"])
    with pytest.raises(ValueError):
        check_conformance(events=[{"case_id": "c", "activity": "A", "timestamp": "2024-01-01T00:00:00Z"}], designed_activities=[])
