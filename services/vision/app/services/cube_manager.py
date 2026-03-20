"""
OLAP 큐브 관리 서비스.

VisionRuntime에서 분리된 큐브 생성/조회 + 피벗 SQL 실행 담당 클래스.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.services._utils import utc_now_iso as _now
from app.services.exceptions import PivotQueryTimeoutError  # noqa: F401 — 하위 호환용 re-export
from app.services.vision_state_store import VisionStateStore

logger = logging.getLogger(__name__)


class CubeManager:
    """
    OLAP 큐브 생성/조회 및 피벗 SQL 실행을 담당하는 매니저.

    - store: 영구 저장소 (VisionStateStore)
    - id_generator: 고유 ID를 생성하는 콜백 함수
    - cubes: 큐브 메모리 캐시 딕셔너리 (VisionRuntime과 같은 참조 공유)
    """

    def __init__(
        self,
        store: VisionStateStore,
        id_generator: Callable[[str], str],
        cubes: dict[str, dict[str, Any]],
    ) -> None:
        self._store = store
        self._new_id = id_generator
        self._cubes = cubes

    def create_cube(
        self,
        cube_name: str,
        fact_table: str,
        dimensions: list[str],
        measures: list[str],
        dimension_details: list[dict[str, Any]] | None = None,
        measure_details: list[dict[str, Any]] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """큐브 정의를 생성하고 저장소에 기록."""
        now = _now()
        cube: dict[str, Any] = {
            "name": cube_name,
            "fact_table": fact_table,
            "dimensions": dimensions,
            "measures": measures,
            "dimension_count": len(dimensions),
            "measure_count": len(measures),
            "last_refreshed": now,
            "row_count": 1000,
        }
        if dimension_details is not None:
            cube["dimension_details"] = dimension_details
        if measure_details is not None:
            cube["measure_details"] = measure_details
        cube.update(extra)
        self._cubes[cube_name] = cube
        self._store.upsert_cube(cube_name, cube)
        return cube

    def execute_pivot_query(
        self,
        sql: str,
        params: list[Any],
        timeout_seconds: int = 30,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        피벗용 읽기 전용 SQL 실행. (rows, column_names) 반환.
        PostgreSQL이 아니거나 실패 시 빈 결과. 타임아웃 시 PivotQueryTimeoutError.
        """
        if not getattr(self._store, "_is_postgres", False):
            return [], []
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            return [], []
        conn = None
        try:
            conn = psycopg2.connect(self._store.database_url)
            conn.set_session(readonly=True)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET statement_timeout = %s", (timeout_seconds * 1000,))
                cur.execute(sql, params)
                rows = cur.fetchall()
                column_names = list(rows[0].keys()) if rows else []
            return [dict(r) for r in rows], column_names
        except Exception as e:
            err_msg = str(e).lower()
            if "timeout" in err_msg or "canceled" in err_msg or "statement_timeout" in err_msg:
                raise PivotQueryTimeoutError() from e
            return [], []
        finally:
            if conn:
                conn.close()
