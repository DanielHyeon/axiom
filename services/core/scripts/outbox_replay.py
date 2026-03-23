#!/usr/bin/env python3
"""
멀티테넌트 프로세스 그래프 — Outbox Replay CLI.

Phase 0 (플랫폼 하드닝): 운영 복구 도구.
미발행(PENDING) 이벤트 재전송, 실패(FAILED) 이벤트 재시도, DLQ 재처리.

사용 예:
    # 미발행 이벤트 건수 확인 (실제 전송 없음)
    python scripts/outbox_replay.py --dry-run

    # 미발행 이벤트 최대 500건 재전송
    python scripts/outbox_replay.py --limit 500

    # FAILED 이벤트를 PENDING으로 복구 후 재전송
    python scripts/outbox_replay.py --retry-failed --limit 100
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select, update

# 프로젝트 루트에서 실행하도록 경로 보정
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("axiom.scripts.outbox_replay")


async def get_counts(session) -> dict[str, int]:
    """이벤트 상태별 건수 조회."""
    from app.models.base_models import EventOutbox

    result = await session.execute(
        select(EventOutbox.status, func.count())
        .group_by(EventOutbox.status)
    )
    return {row[0]: row[1] for row in result.all()}


async def retry_failed(session, limit: int) -> int:
    """FAILED 상태 이벤트를 PENDING으로 복구한다."""
    from app.models.base_models import EventOutbox

    result = await session.execute(
        update(EventOutbox)
        .where(EventOutbox.status == "FAILED")
        .values(status="PENDING", retry_count=0)
        .returning(EventOutbox.id)
    )
    ids = result.scalars().all()
    await session.commit()
    return len(ids)


async def replay(limit: int, retry_failed_flag: bool, dry_run: bool) -> None:
    """메인 실행 로직."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # 현재 상태 리포트
        counts = await get_counts(session)
        logger.info("=== Outbox 상태 현황 ===")
        for status_name, count in sorted(counts.items()):
            logger.info("  %s: %d건", status_name, count)

        if dry_run:
            logger.info("--dry-run 모드: 실제 처리 없이 종료합니다.")
            return

        # FAILED → PENDING 복구
        if retry_failed_flag:
            recovered = await retry_failed(session, limit)
            logger.info("FAILED → PENDING 복구: %d건", recovered)

    # SyncWorker를 통한 실제 전송
    from app.workers.sync import SyncWorker
    worker = SyncWorker(poll_interval_seconds=0, max_batch=limit)
    result = await worker.publish_pending_once()
    published = result.get("published", 0)
    failed = result.get("failed", 0)
    logger.info("전송 완료: published=%d, failed=%d", published, failed)

    # 결과 확인
    async with AsyncSessionLocal() as session:
        counts = await get_counts(session)
        logger.info("=== 처리 후 상태 ===")
        for status_name, count in sorted(counts.items()):
            logger.info("  %s: %d건", status_name, count)


def main():
    parser = argparse.ArgumentParser(
        description="Axiom Outbox Replay CLI — 미발행 이벤트 재전송 도구",
    )
    parser.add_argument("--limit", type=int, default=1000, help="최대 처리 건수 (기본: 1000)")
    parser.add_argument("--retry-failed", action="store_true", help="FAILED 이벤트를 PENDING으로 복구 후 재전송")
    parser.add_argument("--dry-run", action="store_true", help="상태 확인만 수행 (실제 전송 없음)")
    args = parser.parse_args()

    logger.info(
        "Outbox Replay 시작: limit=%d, retry_failed=%s, dry_run=%s",
        args.limit, args.retry_failed, args.dry_run,
    )
    asyncio.run(replay(args.limit, args.retry_failed, args.dry_run))
    logger.info("Outbox Replay 완료.")


if __name__ == "__main__":
    main()
