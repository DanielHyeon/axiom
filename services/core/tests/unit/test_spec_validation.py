import pytest

from app.services.process_service import ProcessDomainError, ProcessService
from app.services.watch_service import WatchDomainError, WatchService


@pytest.mark.asyncio
async def test_process_definition_source_validation():
    with pytest.raises(ProcessDomainError, match="source must be"):
        await ProcessService.create_definition(
            db=None,  # type: ignore[arg-type]
            tenant_id="t1",
            name="invalid",
            source="yaml",
        )


def test_watch_rule_validation_threshold_requires_all_fields():
    with pytest.raises(WatchDomainError, match="threshold rule requires"):
        WatchService._validate_rule(
            {"type": "threshold", "field": "cash_ratio", "operator": "<"}
        )


def test_watch_rule_validation_accepts_deadline():
    WatchService._validate_rule({"type": "deadline", "days_before": 7})
