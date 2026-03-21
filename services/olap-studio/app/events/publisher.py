"""이벤트 발행 헬퍼 — API 라우터에서 사용하는 고수준 함수.

각 도메인 이벤트마다 명시적 함수를 두어 타입 안전성과 가독성을 확보한다.
내부적으로 outbox.publish_event()를 호출하여 Transactional Outbox 패턴을 따른다.
"""
from __future__ import annotations

from app.events.outbox import publish_event


async def emit_etl_run_completed(
    tenant_id: str,
    project_id: str,
    pipeline_id: str,
    run_id: str,
    status: str,
    rows_read: int,
    rows_written: int,
    duration_ms: int,
) -> None:
    """ETL 실행 완료 이벤트 발행."""
    await publish_event(
        tenant_id=tenant_id,
        project_id=project_id,
        aggregate_type="etl_pipeline",
        aggregate_id=pipeline_id,
        event_type="olap.etl.run.completed",
        payload={
            "pipelineId": pipeline_id,
            "runId": run_id,
            "status": status,
            "rowsRead": rows_read,
            "rowsWritten": rows_written,
            "durationMs": duration_ms,
        },
    )


async def emit_cube_published(
    tenant_id: str,
    project_id: str,
    cube_id: str,
    model_id: str,
    cube_name: str,
    version_no: int,
) -> None:
    """큐브 게시 완료 이벤트 발행."""
    await publish_event(
        tenant_id=tenant_id,
        project_id=project_id,
        aggregate_type="cube",
        aggregate_id=cube_id,
        event_type="olap.cube.published",
        payload={
            "cubeId": cube_id,
            "modelId": model_id,
            "cubeName": cube_name,
            "versionNo": version_no,
        },
    )


async def emit_lineage_updated(
    tenant_id: str,
    project_id: str,
    entity_count: int,
    edge_count: int,
    root_entity_type: str,
    root_entity_id: str,
) -> None:
    """리니지 갱신 완료 이벤트 발행."""
    await publish_event(
        tenant_id=tenant_id,
        project_id=project_id,
        aggregate_type="lineage",
        aggregate_id=root_entity_id,
        event_type="olap.lineage.updated",
        payload={
            "entityCount": entity_count,
            "edgeCount": edge_count,
            "rootEntityType": root_entity_type,
            "rootEntityId": root_entity_id,
        },
    )


async def emit_ai_cube_generated(
    tenant_id: str,
    project_id: str,
    generation_id: str,
    cube_id: str | None,
    confidence: float,
    requires_review: bool,
) -> None:
    """AI 큐브 생성 완료 이벤트 발행."""
    await publish_event(
        tenant_id=tenant_id,
        project_id=project_id,
        aggregate_type="ai_generation",
        aggregate_id=generation_id,
        event_type="olap.ai.cube.generated",
        payload={
            "generationId": generation_id,
            "cubeId": cube_id,
            "confidence": confidence,
            "requiresReview": requires_review,
        },
    )
