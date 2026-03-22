"""
품질 수집 백그라운드 워커 — 주기적으로 시멘틱 계약 대상의 품질을 수집한다.

WeaverRelayWorker 패턴을 따라:
1. poll_interval_seconds마다 Synapse에서 approved 엔티티 목록을 조회
2. 각 엔티티의 physical_source_ref에 대해 품질 스캔 실행
3. 결과를 quality_scores 테이블에 저장
4. (P2 §4.5) Redis Stream 이벤트 수신 시 즉시 스캔 트리거 (5분 중복 방지)

Synapse 연결 실패 시 graceful skip하고 다음 주기에 재시도.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.events.outbox import EventPublisher
from app.services.insight_store import insight_store
from app.services.quality_collector import QualityCollector

logger = logging.getLogger("weaver.quality_worker")

# 이벤트 기반 스캔 중복 방지 시간 (분)
EVENT_DEDUP_MINUTES = 5

# 품질 임계값 — 이 점수 미만이면 QUALITY_THRESHOLD_BREACHED 이벤트 발행
QUALITY_BREACH_THRESHOLD = 60

# 기본 수집 주기: 15분
DEFAULT_POLL_INTERVAL = 900


class QualityWorker:
    """주기적 품질 수집 백그라운드 워커"""

    def __init__(self, poll_interval: int = DEFAULT_POLL_INTERVAL):
        self._poll = poll_interval
        self._running = True
        self._collector = QualityCollector(insight_store)
        self._synapse_url = (getattr(settings, "synapse_base_url", "") or "http://localhost:8003").rstrip("/")
        self._service_token = getattr(settings, "weaver_insight_service_token", "") or ""

    async def run(self) -> None:
        """메인 루프 — 주기적으로 품질 수집 실행"""
        logger.info("QualityWorker started (poll=%ds)", self._poll)
        # 첫 실행은 30초 후 (서비스 안정화 대기)
        await asyncio.sleep(30)
        while self._running:
            try:
                stats = await self._collect_once()
                logger.info("quality_collection_cycle_done", extra=stats)
            except asyncio.CancelledError:
                logger.info("QualityWorker cancelled")
                break
            except Exception:
                logger.exception("quality_collection_cycle_failed")
            await asyncio.sleep(self._poll)

    async def _collect_once(self) -> dict[str, int]:
        """한 주기: Synapse에서 approved 엔티티 조회 → 각 테이블 품질 스캔"""
        entities = await self._fetch_approved_entities()
        if not entities:
            return {"scanned": 0, "skipped": 0, "errors": 0}

        scanned = 0
        skipped = 0
        errors = 0

        for entity in entities:
            source_ref = entity.get("physical_source_ref", "")
            entity_id = entity.get("entity_id", "")
            if not source_ref:
                skipped += 1
                continue

            try:
                # tenant_id는 엔티티에서 가져옴
                tenant_id = entity.get("tenant_id", "")
                if not tenant_id:
                    skipped += 1
                    continue

                target_id = f"{entity_id}:{source_ref}"

                # 이전 점수 조회 — breach 이벤트에 previous_score 포함하기 위해
                previous = await self._collector.get_score_for_target(
                    tenant_id=tenant_id,
                    target_type="table",
                    target_id=target_id,
                )
                previous_score = float(previous["overall_score"]) if previous else None

                # 품질 스캔 실행
                result = await self._collector.collect_table_quality(
                    tenant_id=tenant_id,
                    datasource_id=entity_id,  # entity_id를 datasource 식별자로 사용
                    table_name=source_ref,
                    freshness_sla_minutes=entity.get("freshness_sla_minutes"),
                    owner_team=entity.get("owner_team"),
                )
                scanned += 1

                # §3.3 이벤트 발행 — 스캔 완료 후 항상 QUALITY_SCORE_UPDATED
                await self._publish_score_updated(entity_id, tenant_id, result)

                # §3.3 이벤트 발행 — 임계값 미달 시 QUALITY_THRESHOLD_BREACHED
                overall = result.get("overall_score", 100)
                if overall < QUALITY_BREACH_THRESHOLD:
                    await self._publish_threshold_breached(
                        entity_id, tenant_id, result, previous_score,
                    )
            except Exception as exc:
                logger.warning("quality_scan_failed", entity_id=entity_id, error=str(exc))
                errors += 1

        return {"scanned": scanned, "skipped": skipped, "errors": errors}

    async def _fetch_approved_entities(self) -> list[dict[str, Any]]:
        """Synapse semantic API에서 approved 엔티티 목록을 가져온다."""
        url = f"{self._synapse_url}/api/v3/synapse/semantic/entities"
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers, params={"limit": 200})
                resp.raise_for_status()
                body = resp.json()
        except Exception as exc:
            logger.warning("synapse_entity_fetch_failed", error=str(exc))
            return []

        all_entities = body.get("data") or []
        # approved만 필터 (Synapse API에 status 필터가 없는 경우 대비)
        return [e for e in all_entities if e.get("status") == "approved"]

    # ── §3.3 이벤트 발행 헬퍼 ──

    async def _publish_score_updated(
        self, entity_id: str, tenant_id: str, result: dict[str, Any],
    ) -> None:
        """QUALITY_SCORE_UPDATED 이벤트 — 스캔 완료 시 항상 발행"""
        try:
            payload = {
                "target_id": result.get("target_id", ""),
                "overall_score": result.get("overall_score", 0),
                "formula_version": result.get("formula_version", 2),
                "dimension_scores": result.get("scores", {}),
                "scanned_at": result.get("sampled_at", ""),
            }
            await EventPublisher.publish(
                event_type="QUALITY_SCORE_UPDATED",
                aggregate_type="quality_score",
                aggregate_id=entity_id,
                payload=payload,
                tenant_id=tenant_id,
            )
        except Exception:
            # 이벤트 발행 실패는 스캔 결과에 영향 없음 — 로그만 남긴다
            logger.warning("quality_score_updated_event_failed", entity_id=entity_id, exc_info=True)

    async def _publish_threshold_breached(
        self, entity_id: str, tenant_id: str, result: dict[str, Any],
        previous_score: float | None,
    ) -> None:
        """QUALITY_THRESHOLD_BREACHED 이벤트 — overall_score < 60 일 때 발행"""
        try:
            # 임계값 미달인 차원 목록 추출 (개별 차원도 60 미만인 것들)
            breached_dims = [
                dim for dim, score in (result.get("scores") or {}).items()
                if score is not None and score < QUALITY_BREACH_THRESHOLD
            ]
            payload = {
                "target_id": result.get("target_id", ""),
                "overall_score": result.get("overall_score", 0),
                "breached_dimensions": breached_dims,
                "previous_score": previous_score,
                "scanned_at": result.get("sampled_at", ""),
            }
            await EventPublisher.publish(
                event_type="QUALITY_THRESHOLD_BREACHED",
                aggregate_type="quality_score",
                aggregate_id=entity_id,
                payload=payload,
                tenant_id=tenant_id,
            )
        except Exception:
            logger.warning("quality_threshold_breached_event_failed", entity_id=entity_id, exc_info=True)

    # ── P2 §4.5: 이벤트 기반 즉시 스캔 트리거 ──

    async def handle_entity_published(
        self, tenant_id: str, entity_id: str, physical_source_ref: str,
    ) -> dict[str, Any]:
        """SEMANTIC_ENTITY_PUBLISHED 이벤트 수신 시 즉시 품질 스캔 트리거.

        최근 5분 이내 동일 엔티티 스캔 이력이 있으면 중복 방지를 위해 스킵한다.
        """
        target_id = f"{entity_id}:{physical_source_ref}"

        if not await self._should_scan(tenant_id, entity_id, physical_source_ref):
            logger.info(
                "event_quality_scan_skipped (dedup 5min)",
                extra={"tenant_id": tenant_id, "target_id": target_id},
            )
            return {"action": "skipped", "reason": "recent_scan_exists", "target_id": target_id}

        logger.info(
            "event_quality_scan_triggered",
            extra={"tenant_id": tenant_id, "target_id": target_id},
        )

        try:
            result = await self._collector.collect_table_quality(
                tenant_id=tenant_id,
                datasource_id=entity_id,
                table_name=physical_source_ref,
            )
            # 스캔 완료 이벤트 발행
            await self._publish_score_updated(entity_id, tenant_id, result)

            # 임계값 미달 시 breach 이벤트 발행
            overall = result.get("overall_score", 100)
            if overall < QUALITY_BREACH_THRESHOLD:
                await self._publish_threshold_breached(entity_id, tenant_id, result, None)

            return {"action": "scanned", "target_id": target_id, "overall_score": overall}
        except Exception as exc:
            logger.warning(
                "event_quality_scan_failed",
                extra={"tenant_id": tenant_id, "target_id": target_id, "error": str(exc)},
            )
            return {"action": "error", "target_id": target_id, "error": str(exc)}

    async def _should_scan(self, tenant_id: str, entity_id: str, table_name: str) -> bool:
        """최근 5분 이내 스캔 이력이 있으면 스킵"""
        target_id = f"{entity_id}:{table_name}"
        try:
            last = await self._collector.get_score_for_target(
                tenant_id, "table", target_id,
            )
        except Exception:
            # DB 조회 실패 시 안전하게 스캔 진행
            return True

        if not last:
            return True  # 스캔 이력 없음 → 즉시 스캔

        if last_time := last.get("created_at"):
            if isinstance(last_time, str):
                last_time = datetime.fromisoformat(last_time)
            if hasattr(last_time, "replace") and last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_time < timedelta(minutes=EVENT_DEDUP_MINUTES):
                return False  # 5분 이내 스캔됨 → 스킵
        return True

    def shutdown(self) -> None:
        self._running = False
