"""
MiningTaskCoordinator — 마이닝 태스크 라이프사이클 관리 (DDD-P2-04).

ProcessMiningService에서 추출한 태스크 생성/조회/완료/캐시 책임.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.services.mining_store import get_mining_store
from app.services.mining_utils import utcnow_iso


class MiningTaskError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class MiningTask:
    tenant_id: str
    task_id: str
    task_type: str
    case_id: str
    log_id: str
    status: str
    created_at: str
    updated_at: str
    requested_by: str | None
    started_at: str | None = None
    completed_at: str | None = None
    result_id: str | None = None
    error: dict[str, Any] | None = None


def task_from_row(row: dict[str, Any]) -> MiningTask:
    """Store 행 또는 dict를 MiningTask로 변환."""
    return MiningTask(
        tenant_id=row["tenant_id"],
        task_id=row["task_id"],
        task_type=row["task_type"],
        case_id=row["case_id"],
        log_id=row["log_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        requested_by=row.get("requested_by"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        result_id=row.get("result_id"),
        error=row.get("error"),
    )


class MiningTaskCoordinator:
    """마이닝 태스크 생성·상태 전이·결과 저장·조회를 전담."""

    def __init__(self, max_active_tasks: int = 8) -> None:
        self._tasks: dict[str, MiningTask] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._models: dict[str, dict[str, Any]] = {}
        self._max_active_tasks = max_active_tasks
        self._store = get_mining_store()
        self._hydrate_from_store()

    def _hydrate_from_store(self) -> None:
        if not self._store:
            return
        try:
            self._store._ensure_schema()
            conn = self._store._connect()
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                cursor_cls = RealDictCursor
            except Exception:
                conn.close()
                return
            cur = conn.cursor(cursor_factory=cursor_cls)
            cur.execute(
                "SELECT task_id, tenant_id, task_type, case_id, log_id, status, "
                "result_id, created_at, started_at, completed_at, updated_at, "
                "requested_by, error FROM mining_tasks ORDER BY created_at DESC LIMIT 200"
            )
            for row in cur.fetchall():
                d = dict(row)
                for key in ("created_at", "started_at", "completed_at", "updated_at"):
                    if d.get(key) and hasattr(d[key], "isoformat"):
                        d[key] = d[key].isoformat()
                self._tasks[d["task_id"]] = task_from_row(d)
            cur.close()
            conn.close()
        except Exception:
            pass

    def clear(self) -> None:
        self._tasks.clear()
        self._results.clear()
        self._models.clear()
        if self._store:
            self._store.clear()

    @property
    def store(self):
        return self._store

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self._models

    def require_rate_limit(self) -> None:
        if self._store:
            active = self._store.count_active_tasks()
        else:
            active = sum(1 for t in self._tasks.values() if t.status in {"queued", "running"})
        if active >= self._max_active_tasks:
            raise MiningTaskError(429, "MINING_RATE_LIMIT", "too many running tasks")

    def create_task(
        self, tenant_id: str, task_type: str, case_id: str, log_id: str, requested_by: str | None,
    ) -> MiningTask:
        task_id = f"task-pm-{uuid.uuid4()}"
        now = utcnow_iso()
        if self._store:
            self._store.insert_task(task_id, tenant_id, task_type, case_id, log_id, requested_by)
        task = MiningTask(
            tenant_id=tenant_id, task_id=task_id, task_type=task_type,
            case_id=case_id, log_id=log_id, status="queued",
            created_at=now, updated_at=now, requested_by=requested_by,
        )
        self._tasks[task_id] = task
        return task

    def set_running(self, task: MiningTask) -> None:
        now = utcnow_iso()
        if self._store:
            self._store.set_running(task.task_id)
        task.status = "running"
        task.started_at = now
        task.updated_at = now

    def set_completed(self, task: MiningTask, result_payload: dict[str, Any]) -> dict[str, Any]:
        now = utcnow_iso()
        result_id = f"pm-result-{uuid.uuid4()}"
        if self._store:
            self._store.set_completed(task.task_id, result_id, result_payload)
        task.status = "completed"
        task.result_id = result_id
        task.completed_at = now
        task.updated_at = now
        data = {
            "id": result_id, "task_id": task.task_id, "task_type": task.task_type,
            "case_id": task.case_id, "log_id": task.log_id, "created_at": now,
            "result": result_payload,
        }
        self._results[result_id] = data
        return data

    def task_or_404(self, tenant_id: str, task_id: str) -> MiningTask:
        if self._store:
            row = self._store.get_task(tenant_id, task_id)
            if row:
                return task_from_row(row)
        task = self._tasks.get(task_id)
        if not task or task.tenant_id != tenant_id:
            raise MiningTaskError(404, "TASK_NOT_FOUND", "task not found")
        return task

    def result_or_404(self, tenant_id: str, result_or_task_id: str) -> dict[str, Any]:
        if self._store:
            result = self._store.get_result(tenant_id, result_or_task_id)
            if result:
                return result
            result = self._store.get_result_by_task_id(tenant_id, result_or_task_id)
            if result:
                return result
            raise MiningTaskError(404, "RESULT_NOT_FOUND", "result not found")
        result = self._results.get(result_or_task_id)
        if result:
            if self._tasks[result["task_id"]].tenant_id != tenant_id:
                raise MiningTaskError(404, "RESULT_NOT_FOUND", "result not found")
            return result
        task = self._tasks.get(result_or_task_id)
        if task and task.tenant_id == tenant_id and task.result_id:
            return self._results[task.result_id]
        raise MiningTaskError(404, "RESULT_NOT_FOUND", "result not found")

    def get_task_dict(self, tenant_id: str, task_id: str) -> dict[str, Any]:
        task = self.task_or_404(tenant_id, task_id)
        return {
            "task_id": task.task_id, "task_type": task.task_type, "status": task.status,
            "case_id": task.case_id, "log_id": task.log_id, "result_id": task.result_id,
            "created_at": task.created_at, "started_at": task.started_at,
            "updated_at": task.updated_at, "completed_at": task.completed_at,
            "error": task.error,
        }

    def get_task_result_dict(self, tenant_id: str, task_id: str) -> dict[str, Any]:
        task = self.task_or_404(tenant_id, task_id)
        if not task.result_id:
            raise MiningTaskError(404, "RESULT_NOT_FOUND", "result not found")
        return self.result_or_404(tenant_id, task.result_id)

    def get_result_dict(self, tenant_id: str, result_or_task_id: str) -> dict[str, Any]:
        return self.result_or_404(tenant_id, result_or_task_id)
