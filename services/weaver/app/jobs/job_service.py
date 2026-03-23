"""G35: Job Service — 공통 작업 관리 서비스.

모든 장시간 작업의 생성·조회·상태 전환·재시도·취소를 관리한다.
in-memory 저장소로 시작하며, Phase 1에서 PostgreSQL weaver.job_runs로 전환한다.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.models.job import ArtifactRef, JobRun, JobStatus, JobStep, JobType, RetryPolicy

logger = logging.getLogger("axiom.weaver.jobs")


class JobService:
    """공통 작업 관리 — 생성, 조회, heartbeat, 완료/실패/취소.

    in-memory 저장소 + asyncio.Lock으로 동시성 보호.
    Phase 1에서 PostgreSQL weaver.job_runs로 전환 시 Lock → DB 트랜잭션으로 교체.
    """

    def __init__(self) -> None:
        # in-memory 저장소 (Phase 1에서 PostgreSQL로 전환)
        self._jobs: dict[str, JobRun] = {}
        # idempotency_key → run_id 매핑
        self._idempotency_index: dict[str, str] = {}
        # 동시성 보호 (리뷰 #7 반영)
        self._lock = asyncio.Lock()

    async def create(
        self,
        job_type: JobType,
        tenant_id: str,
        triggered_by: str,
        idempotency_key: str | None = None,
        parent_run_id: str | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> JobRun:
        """새 작업 생성 — 동일 idempotency_key면 기존 run 반환."""
        async with self._lock:
            # 중복 실행 방지 (atomic read-check-write)
            if idempotency_key and idempotency_key in self._idempotency_index:
                existing_id = self._idempotency_index[idempotency_key]
                existing = self._jobs.get(existing_id)
                if existing and existing.status in (JobStatus.PENDING, JobStatus.RUNNING):
                    logger.info("중복 요청 감지 — 기존 작업 반환: %s", existing_id)
                    return existing

            job = JobRun(
                job_type=job_type,
                tenant_id=tenant_id,
                triggered_by=triggered_by,
                idempotency_key=idempotency_key,
                parent_run_id=parent_run_id,
                retry_policy=retry_policy or RetryPolicy(),
            )
            self._jobs[job.run_id] = job
            if idempotency_key:
                self._idempotency_index[idempotency_key] = job.run_id

        logger.info("작업 생성: %s (type=%s, tenant=%s)", job.run_id, job_type, tenant_id)
        return job

    def get(self, run_id: str) -> JobRun | None:
        """작업 조회"""
        return self._jobs.get(run_id)

    def list_by_tenant(
        self,
        tenant_id: str,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[JobRun]:
        """테넌트별 작업 목록 조회"""
        result = []
        for job in self._jobs.values():
            if job.tenant_id != tenant_id:
                continue
            if job_type and job.job_type != job_type:
                continue
            if status and job.status != status:
                continue
            result.append(job)
        # 최신 순 정렬
        result.sort(key=lambda j: j.created_at, reverse=True)
        return result[:limit]

    def start(self, run_id: str, worker_id: str) -> JobRun | None:
        """작업 시작"""
        job = self._jobs.get(run_id)
        if not job:
            return None
        job.start(worker_id)
        logger.info("작업 시작: %s (worker=%s)", run_id, worker_id)
        return job

    def heartbeat(self, run_id: str) -> bool:
        """워커 heartbeat 갱신"""
        job = self._jobs.get(run_id)
        if not job or job.status != JobStatus.RUNNING:
            return False
        job.heartbeat()
        return True

    def complete(self, run_id: str, checksum: str | None = None) -> JobRun | None:
        """작업 완료"""
        job = self._jobs.get(run_id)
        if not job:
            return None
        job.complete(checksum)
        logger.info("작업 완료: %s", run_id)
        return job

    def fail(self, run_id: str, error: str) -> JobRun | None:
        """작업 실패"""
        job = self._jobs.get(run_id)
        if not job:
            return None
        job.fail(error)
        logger.warning("작업 실패: %s — %s", run_id, error)
        return job

    def cancel(self, run_id: str) -> JobRun | None:
        """작업 취소"""
        job = self._jobs.get(run_id)
        if not job or job.status not in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.PAUSED):
            return None
        job.cancel()
        logger.info("작업 취소: %s", run_id)
        return job

    def update_progress(self, run_id: str, progress: float) -> bool:
        """진행률 업데이트"""
        job = self._jobs.get(run_id)
        if not job:
            return False
        job.progress = min(max(progress, 0.0), 1.0)
        return True

    def detect_stale_jobs(self) -> list[JobRun]:
        """만료된(stale) 작업 감지 — 스케줄러에서 주기적 호출"""
        stale = []
        for job in self._jobs.values():
            if job.is_stale():
                job.status = JobStatus.STALE
                stale.append(job)
                logger.warning("좀비 작업 감지: %s (worker=%s)", job.run_id, job.worker_id)
        return stale


# 모듈 수준 싱글톤
job_service = JobService()
