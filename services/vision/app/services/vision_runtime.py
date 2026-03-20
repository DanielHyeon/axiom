"""
VisionRuntime — Facade 패턴.

모든 Vision 서비스의 진입점 역할. 내부적으로 책임별 서브 서비스에 위임한다.
기존 public API (메서드 시그니처)를 100% 유지하여 API 레이어 변경 없이 작동.

서브 서비스 구조:
- ScenarioManager   : 시나리오(What-If) CRUD + 솔버 실행
- CubeManager       : OLAP 큐브 생성/조회 + 피벗 SQL 실행
- EtlManager        : ETL 동기화 작업 큐잉/실행/상태 관리
- RootCauseService  : 근본 원인 분석 생성/조회/반사실/타임라인/영향도/그래프
- OperationalMetricsCollector : 운영 메트릭 수집/렌더링
- CausalAnalysisService      : 인과 분석(VAR/Granger) 실행/조회
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from itertools import count
from typing import Any

from app.engines.causal_analysis_engine import CausalAnalysisEngine
from app.services._utils import utc_now_iso as _now  # noqa: F401 — 하위 호환용
from app.services.causal_analysis_service import CausalAnalysisService
from app.services.causal_data_fetcher import CausalDataFetcher
from app.services.cube_manager import CubeManager
from app.services.etl_manager import EtlManager
from app.services.exceptions import PivotQueryTimeoutError  # noqa: F401 — 하위 호환용 re-export
from app.services.exceptions import VisionRuntimeError  # noqa: F401 — 하위 호환용 re-export
from app.services.operational_metrics import OperationalMetricsCollector
from app.services.root_cause_service import RootCauseService
from app.services.scenario_manager import ScenarioManager
from app.services.vision_state_store import VisionStateStore

logger = logging.getLogger(__name__)


class VisionRuntime:
    """
    Vision 서비스 Facade.

    모든 public 메서드는 내부 서브 서비스에 위임한다.
    기존 코드에서 `vision_runtime.xxx()`로 호출하던 것이 동일하게 작동.
    """

    def __init__(self, store: VisionStateStore | None = None) -> None:
        # ── 저장소 & 상태 로드 ── #
        self.store = store or VisionStateStore(
            os.getenv("VISION_STATE_DATABASE_URL", "postgresql://arkos:arkos@localhost:5432/insolvency_os")
        )
        loaded = self.store.load_state()

        # 메모리 캐시 (서브 서비스들이 같은 참조를 공유)
        self.what_if_by_case: dict[str, dict[str, dict[str, Any]]] = loaded.get("what_if_by_case", {})
        self.cubes: dict[str, dict[str, Any]] = loaded.get("cubes", {})
        self.etl_jobs: dict[str, dict[str, Any]] = loaded.get("etl_jobs", {})
        self.root_cause_by_case: dict[str, dict[str, Any]] = loaded.get("root_cause_by_case", {})
        self.causal_results_by_case: dict[str, dict[str, dict[str, Any]]] = loaded.get("causal_results_by_case", {})

        # ID 생성기 (모든 서브 서비스가 공유)
        self._id_seq = count(1)

        # ── 서브 서비스 초기화 ── #
        self._scenarios = ScenarioManager(self.store, self._new_id, self.what_if_by_case)
        self._cubes = CubeManager(self.store, self._new_id, self.cubes)
        self._etl = EtlManager(self.store, self._new_id, self.etl_jobs)
        self._rca = RootCauseService(self.store, self._new_id, self.root_cause_by_case)
        self._metrics = OperationalMetricsCollector()

        # 인과 분석 엔진 + 데이터 수집기
        causal_engine = CausalAnalysisEngine(
            significance_level=float(os.getenv("CAUSAL_SIGNIFICANCE_LEVEL", "0.05")),
            min_correlation=float(os.getenv("CAUSAL_MIN_CORRELATION", "0.3")),
            max_lag=int(os.getenv("CAUSAL_MAX_LAG", "2")),
        )
        causal_fetcher = CausalDataFetcher(
            synapse_url=os.getenv("SYNAPSE_BASE_URL"),
            weaver_url=os.getenv("WEAVER_BASE_URL"),
        )
        self._causal = CausalAnalysisService(
            causal_engine, causal_fetcher, self._new_id, self.causal_results_by_case
        )

    # ── ID 생성 유틸 ── #

    def _new_id(self, prefix: str) -> str:
        """고유 ID 생성 (타임스탬프 + 시퀀스 조합)."""
        return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000)}-{next(self._id_seq)}"

    # ── 전체 초기화 ── #

    def clear(self) -> None:
        """모든 인메모리 상태 + 저장소 초기화."""
        self.what_if_by_case.clear()
        self.cubes.clear()
        self.etl_jobs.clear()
        self.root_cause_by_case.clear()
        self.causal_results_by_case.clear()
        self.store.clear()
        self._metrics.reset()

    # ── 시나리오(What-If) 위임 ── #

    def scenarios(self, case_id: str) -> dict[str, dict[str, Any]]:
        return self._scenarios.scenarios(case_id)

    def create_scenario(self, case_id: str, payload: dict[str, Any], created_by: str) -> dict[str, Any]:
        return self._scenarios.create_scenario(case_id, payload, created_by)

    def save_scenario(self, case_id: str, scenario: dict[str, Any]) -> None:
        return self._scenarios.save_scenario(case_id, scenario)

    def list_scenarios(self, case_id: str) -> list[dict[str, Any]]:
        return self._scenarios.list_scenarios(case_id)

    def get_scenario(self, case_id: str, scenario_id: str) -> dict[str, Any] | None:
        return self._scenarios.get_scenario(case_id, scenario_id)

    def delete_scenario(self, case_id: str, scenario_id: str) -> bool:
        return self._scenarios.delete_scenario(case_id, scenario_id)

    def set_scenario_computing(self, case_id: str, scenario_id: str) -> None:
        return self._scenarios.set_scenario_computing(case_id, scenario_id)

    def set_scenario_failed(self, case_id: str, scenario_id: str, reason: str) -> None:
        return self._scenarios.set_scenario_failed(case_id, scenario_id, reason)

    def run_scenario_solver(self, case_id: str, scenario_id: str) -> dict[str, Any] | None:
        return self._scenarios.run_scenario_solver(case_id, scenario_id)

    # ── 큐브(OLAP) 위임 ── #

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
        return self._cubes.create_cube(
            cube_name, fact_table, dimensions, measures,
            dimension_details=dimension_details, measure_details=measure_details, **extra,
        )

    def execute_pivot_query(
        self, sql: str, params: list[Any], timeout_seconds: int = 30,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        return self._cubes.execute_pivot_query(sql, params, timeout_seconds)

    # ── ETL 위임 ── #

    def queue_etl_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._etl.queue_etl_job(payload)

    def get_etl_job(self, job_id: str) -> dict[str, Any] | None:
        return self._etl.get_etl_job(job_id)

    def complete_etl_job_if_queued(self, job_id: str) -> dict[str, Any] | None:
        return self._etl.complete_etl_job_if_queued(job_id)

    def run_etl_refresh_sync(self, job_id: str) -> None:
        return self._etl.run_etl_refresh_sync(job_id)

    # ── 근본 원인 분석(RCA) 위임 ── #

    def create_root_cause_analysis(
        self, case_id: str, payload: dict[str, Any], requested_by: str
    ) -> dict[str, Any]:
        return self._rca.create_root_cause_analysis(case_id, payload, requested_by)

    def get_root_cause_analysis(self, case_id: str) -> dict[str, Any] | None:
        return self._rca.get_root_cause_analysis(case_id)

    def get_root_cause_status(self, case_id: str) -> dict[str, Any] | None:
        return self._rca.get_root_cause_status(case_id)

    def get_root_causes(self, case_id: str) -> dict[str, Any] | None:
        return self._rca.get_root_causes(case_id)

    def run_counterfactual(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._rca.run_counterfactual(case_id, payload)

    def get_causal_timeline(self, case_id: str) -> dict[str, Any]:
        return self._rca.get_causal_timeline(case_id)

    def get_root_cause_impact(self, case_id: str) -> dict[str, Any]:
        return self._rca.get_root_cause_impact(case_id)

    def get_causal_graph(self, case_id: str) -> dict[str, Any]:
        return self._rca.get_causal_graph(case_id)

    def get_process_bottleneck_root_cause(
        self,
        case_id: str,
        process_id: str,
        bottleneck_activity: str | None = None,
        max_causes: int = 5,
        include_explanation: bool = True,
    ) -> dict[str, Any]:
        return self._rca.get_process_bottleneck_root_cause(
            case_id, process_id, bottleneck_activity, max_causes, include_explanation,
        )

    def run_process_simulation(
        self,
        case_id: str,
        process_model_id: str,
        scenario_name: str,
        description: str | None,
        parameter_changes: list[dict[str, Any]],
        sla_threshold_seconds: int | None,
    ) -> dict[str, Any]:
        return self._rca.run_process_simulation(
            case_id, process_model_id, scenario_name, description,
            parameter_changes, sla_threshold_seconds,
        )

    @property
    def _fetch_synapse_process_context(self):
        """
        Synapse 프로세스 컨텍스트 조회 메서드 접근자.
        테스트에서 monkeypatch.setattr(vision_runtime, "_fetch_synapse_process_context", ...)
        패턴이 동작하도록 property로 노출. setter는 _rca에도 동시 적용.
        """
        return self._rca._fetch_synapse_process_context

    @_fetch_synapse_process_context.setter
    def _fetch_synapse_process_context(self, value):
        """monkeypatch 호환: 패치 시 _rca의 실제 메서드도 교체."""
        self._rca._fetch_synapse_process_context = value

    # ── 운영 메트릭 위임 ── #

    def record_root_cause_call(self, operation: str, success: bool, latency_ms: float) -> None:
        return self._metrics.record_call(operation, success, latency_ms)

    def get_root_cause_operational_metrics(self) -> dict[str, Any]:
        return self._metrics.get_operational_metrics()

    def render_root_cause_metrics_prometheus(self) -> str:
        return self._metrics.render_prometheus()

    # ── 인과 분석 위임 ── #

    async def run_causal_analysis(
        self,
        case_id: str,
        target_node_id: str,
        target_field: str,
        tenant_id: str,
        requested_by: str,
        max_lag: int | None = None,
        significance_level: float | None = None,
    ) -> dict[str, Any]:
        return await self._causal.run_causal_analysis(
            case_id, target_node_id, target_field, tenant_id, requested_by,
            max_lag, significance_level,
        )

    def get_causal_analysis(self, case_id: str, analysis_id: str) -> dict[str, Any] | None:
        return self._causal.get_causal_analysis(case_id, analysis_id)

    def list_causal_analyses(self, case_id: str) -> list[dict[str, Any]]:
        return self._causal.list_causal_analyses(case_id)

    def get_latest_causal_edges(self, case_id: str) -> list[dict[str, Any]]:
        return self._causal.get_latest_causal_edges(case_id)


# 모듈 레벨 싱글톤 — 기존 코드에서 `from ... import vision_runtime` 으로 사용
vision_runtime = VisionRuntime()
