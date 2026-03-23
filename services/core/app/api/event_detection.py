"""G29: 이벤트 탐지 전용 API.

Redis Streams 기반 실시간 이벤트 스트림 조회 + 패턴 매칭 + 통계.
프론트엔드 이벤트 탐지 탭과 연동.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger("axiom.core.api.event_detection")

router = APIRouter(prefix="/api/v3/core/events/detection", tags=["이벤트 탐지"])


# ── 모델 ── #

class EventPattern(BaseModel):
    """이벤트 패턴 정의"""
    pattern_id: str = ""
    name: str
    event_type_filter: str = ""       # 이벤트 타입 필터 (glob 패턴)
    field_conditions: dict = Field(default_factory=dict)  # 필드 조건
    time_window_seconds: int = 300    # 탐지 윈도우 (초)
    min_occurrences: int = 1          # 최소 발생 횟수
    enabled: bool = True


class DetectedEvent(BaseModel):
    """탐지된 이벤트"""
    event_id: str = ""
    event_type: str = ""
    payload: dict = Field(default_factory=dict)
    source: str = ""
    tenant_id: str = ""
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventStatsSummary(BaseModel):
    """이벤트 통계 요약"""
    total_events: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    period_minutes: int = 60


# ── 저장소 (in-memory MVP — Phase 5에서 Redis Streams 직접 조회) ── #

_recent_events: list[DetectedEvent] = []
_patterns: dict[str, EventPattern] = {}
_MAX_EVENTS = 5000


def record_event(event_type: str, payload: dict, source: str = "", tenant_id: str = "") -> str:
    """이벤트 기록 — 다른 모듈에서 호출"""
    import uuid
    event = DetectedEvent(
        event_id=uuid.uuid4().hex[:12],
        event_type=event_type,
        payload=payload,
        source=source,
        tenant_id=tenant_id,
    )
    _recent_events.append(event)
    if len(_recent_events) > _MAX_EVENTS:
        _recent_events[:] = _recent_events[-_MAX_EVENTS // 2:]
    return event.event_id


# ── 엔드포인트 ── #

@router.get("/stream")
async def get_event_stream(
    user: dict = Depends(get_current_user),
    event_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """최근 이벤트 스트림 조회 (테넌트 격리)"""
    tenant_id = user.get("tenant_id", "")
    events = [e for e in _recent_events if e.tenant_id == tenant_id]
    if event_type:
        events = [e for e in events if event_type in e.event_type]
    events = sorted(events, key=lambda e: e.detected_at, reverse=True)[:limit]
    return {"success": True, "data": [e.model_dump(mode="json") for e in events], "total": len(events)}


@router.get("/stats")
async def get_event_stats(
    user: dict = Depends(get_current_user),
    minutes: int = Query(60, ge=1, le=1440),
) -> dict:
    """이벤트 통계 요약"""
    from datetime import timedelta
    tenant_id = user.get("tenant_id", "")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    filtered = [e for e in _recent_events if e.tenant_id == tenant_id and e.detected_at >= cutoff]
    by_type: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for e in filtered:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        by_source[e.source] = by_source.get(e.source, 0) + 1

    return {
        "success": True,
        "data": EventStatsSummary(
            total_events=len(filtered),
            by_type=by_type,
            by_source=by_source,
            period_minutes=minutes,
        ).model_dump(),
    }


# ── 패턴 CRUD ── #

@router.get("/patterns")
async def list_patterns(user: dict = Depends(get_current_user)) -> dict:
    return {"success": True, "data": [p.model_dump() for p in _patterns.values()], "total": len(_patterns)}


@router.post("/patterns")
async def create_pattern(body: EventPattern, user: dict = Depends(get_current_user)) -> dict:
    import uuid
    body.pattern_id = uuid.uuid4().hex[:12]
    _patterns[body.pattern_id] = body
    return {"success": True, "data": body.model_dump()}
