"""
품질 수집 백그라운드 워커 — 주기적으로 시멘틱 계약 대상의 품질을 수집한다.

WeaverRelayWorker 패턴을 따라:
1. poll_interval_seconds마다 Synapse에서 approved 엔티티 목록을 조회
2. 각 엔티티의 physical_source_ref에 대해 품질 스캔 실행
3. 결과를 quality_scores 테이블에 저장

Synapse 연결 실패 시 graceful skip하고 다음 주기에 재시도.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.insight_store import insight_store
from app.services.quality_collector import QualityCollector

logger = logging.getLogger("weaver.quality_worker")

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

                await self._collector.collect_table_quality(
                    tenant_id=tenant_id,
                    datasource_id=entity_id,  # entity_id를 datasource 식별자로 사용
                    table_name=source_ref,
                    freshness_sla_minutes=entity.get("freshness_sla_minutes"),
                    owner_team=entity.get("owner_team"),
                )
                scanned += 1
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

    def shutdown(self) -> None:
        self._running = False
