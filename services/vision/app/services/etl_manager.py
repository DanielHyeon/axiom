"""
ETL 작업 관리 서비스.

VisionRuntime에서 분리된 ETL 작업 큐잉/실행/상태 관리 담당 클래스.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.services._utils import utc_now_iso as _now
from app.services.exceptions import VisionRuntimeError  # noqa: F401 — 하위 호환용 re-export
from app.services.vision_state_store import VisionStateStore

logger = logging.getLogger(__name__)

# ETL: 허용 MV 목록 (etl-pipeline.md 기준). REFRESH MATERIALIZED VIEW CONCURRENTLY만 허용.
ALLOWED_MV_VIEWS = frozenset({
    "mv_business_fact",
    "mv_cashflow_fact",
    "dim_case_type",
    "dim_org",
    "dim_time",
    "dim_stakeholder_type",
})


class EtlManager:
    """
    ETL 동기화 작업 큐잉, 실행(MV Refresh), 상태 관리를 담당하는 매니저.

    - store: 영구 저장소 (VisionStateStore)
    - id_generator: 고유 ID를 생성하는 콜백 함수
    - etl_jobs: ETL 작업 메모리 캐시 딕셔너리 (VisionRuntime과 같은 참조 공유)
    """

    def __init__(
        self,
        store: VisionStateStore,
        id_generator: Callable[[str], str],
        etl_jobs: dict[str, dict[str, Any]],
    ) -> None:
        self._store = store
        self._new_id = id_generator
        self._etl_jobs = etl_jobs

    # ── 상태 확인 ── #

    def _is_etl_running(self) -> bool:
        """진행 중인 ETL 작업이 있으면 True (RUNNING 상태)."""
        return any(
            j.get("status") == "RUNNING"
            for j in self._etl_jobs.values()
        )

    # ── 작업 큐잉/조회 ── #

    def queue_etl_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        """ETL 작업을 큐에 등록. 이미 실행 중이면 VisionRuntimeError 발생."""
        sync_type = str(payload.get("sync_type") or "full").lower()
        target_views = list(payload.get("target_views") or ["mv_business_fact"])
        force = bool(payload.get("force"))
        if not force and self._is_etl_running():
            raise VisionRuntimeError("ETL_IN_PROGRESS", "데이터 동기화가 진행 중입니다")

        job_id = self._new_id("etl-")
        now = _now()
        job: dict[str, Any] = {
            "job_id": job_id,
            "status": "queued",
            "sync_type": sync_type,
            "target_views": target_views,
            "created_at": now,
            "updated_at": now,
            "payload": payload,
        }
        self._etl_jobs[job_id] = job
        self._store.upsert_etl_job(job_id, job)
        return job

    def get_etl_job(self, job_id: str) -> dict[str, Any] | None:
        """ETL 작업 1건 조회."""
        return self._etl_jobs.get(job_id)

    def complete_etl_job_if_queued(self, job_id: str) -> dict[str, Any] | None:
        """큐 상태인 ETL 작업을 완료 처리."""
        job = self.get_etl_job(job_id)
        if not job:
            return None
        if job.get("status") == "queued":
            job["status"] = "completed"
            job["updated_at"] = _now()
            self._store.upsert_etl_job(job_id, job)
        return job

    # ── 실제 ETL 실행 (동기) ── #

    def run_etl_refresh_sync(self, job_id: str) -> None:
        """
        ETL 동기화 실행 (동기). 백그라운드 스레드에서 호출.
        target_views에 대해 REFRESH MATERIALIZED VIEW [CONCURRENTLY] 실행 후
        job 상태를 RUNNING -> COMPLETED/FAILED, duration_seconds, rows_affected 반영.
        """
        job = self.get_etl_job(job_id)
        if not job or job.get("status") != "queued":
            return
        now = _now()
        job["status"] = "RUNNING"
        job["started_at"] = now
        job["updated_at"] = now
        self._store.upsert_etl_job(job_id, job)

        target_views = job.get("target_views") or ["mv_business_fact"]
        views_to_refresh = [v for v in target_views if v in ALLOWED_MV_VIEWS]
        start_monotonic = time.monotonic()
        rows_affected: dict[str, int] = {}

        try:
            if self._store._is_postgres and views_to_refresh:
                psycopg2, _ = self._store._import_psycopg2()
                conn = psycopg2.connect(self._store.database_url)
                try:
                    # REFRESH MATERIALIZED VIEW CONCURRENTLY는 트랜잭션 블록 안에서 실행 불가
                    conn.autocommit = True
                    cur = conn.cursor()
                    for view in views_to_refresh:
                        try:
                            cur.execute(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{view}"')
                        except Exception:
                            # CONCURRENTLY 실패 시 일반 REFRESH 시도
                            cur.execute(f'REFRESH MATERIALIZED VIEW "{view}"')
                    # pg_stat_user_tables에서 대략 행 수 (갱신 후)
                    cur.execute(
                        "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname = ANY(%s)",
                        (list(views_to_refresh),),
                    )
                    for row in cur.fetchall():
                        rows_affected[str(row[0])] = int(row[1] or 0)
                finally:
                    conn.close()
            # SQLite 또는 views_to_refresh 빈 경우: no-op
            elapsed = time.monotonic() - start_monotonic
            job["status"] = "COMPLETED"
            job["completed_at"] = _now()
            job["duration_seconds"] = round(elapsed, 2)
            job["rows_affected"] = rows_affected
            job["updated_at"] = _now()
        except Exception as e:
            job["status"] = "FAILED"
            job["completed_at"] = _now()
            job["duration_seconds"] = round(time.monotonic() - start_monotonic, 2)
            job["error_message"] = str(e)
            job["rows_affected"] = {}
            job["updated_at"] = _now()
        self._store.upsert_etl_job(job_id, job)
