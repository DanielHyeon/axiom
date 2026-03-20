"""
시나리오(What-If) 관리 서비스.

VisionRuntime에서 분리된 시나리오 CRUD + 솔버 실행 담당 클래스.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.engines.scenario_solver import (
    SolverConvergenceError,
    SolverInfeasibleError,
    SolverTimeoutError,
    solve_scenario_result,
    SOLVER_TIMEOUT_SECONDS,
)
from app.services._utils import utc_now_iso as _now
from app.services.vision_state_store import VisionStateStore

logger = logging.getLogger(__name__)


class ScenarioManager:
    """
    시나리오 생성/조회/수정/삭제/솔버 실행을 담당하는 매니저.

    - store: 영구 저장소 (VisionStateStore)
    - id_generator: 고유 ID를 생성하는 콜백 함수
    - what_if_by_case: 케이스별 시나리오를 메모리에 보관하는 딕셔너리
    """

    def __init__(
        self,
        store: VisionStateStore,
        id_generator: Callable[[str], str],
        what_if_by_case: dict[str, dict[str, dict[str, Any]]],
    ) -> None:
        self._store = store
        self._new_id = id_generator
        # 메모리 캐시 — VisionRuntime과 같은 참조를 공유
        self._what_if_by_case = what_if_by_case

    # ── 내부 헬퍼 ── #

    def scenarios(self, case_id: str) -> dict[str, dict[str, Any]]:
        """케이스에 속하는 시나리오 딕셔너리 반환 (없으면 새로 생성)."""
        return self._what_if_by_case.setdefault(case_id, {})

    # ── CRUD ── #

    def create_scenario(
        self, case_id: str, payload: dict[str, Any], created_by: str
    ) -> dict[str, Any]:
        """새 시나리오를 생성하고 저장소에 기록."""
        scenario_id = self._new_id("scn-")
        now = _now()
        scenario: dict[str, Any] = {
            "id": scenario_id,
            "case_id": case_id,
            "scenario_name": payload["scenario_name"],
            "scenario_type": payload["scenario_type"],
            "base_scenario_id": payload.get("base_scenario_id"),
            "description": payload.get("description"),
            "status": "DRAFT",
            "parameters": payload.get("parameters", {}),
            "constraints": payload.get("constraints", []),
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "created_by": created_by,
            "result": None,
        }
        self.scenarios(case_id)[scenario_id] = scenario
        self._store.upsert_scenario(case_id, scenario_id, scenario)
        return scenario

    def save_scenario(self, case_id: str, scenario: dict[str, Any]) -> None:
        """기존 시나리오를 업데이트하고 저장소에 기록."""
        scenario_id = str(scenario.get("id") or "")
        if not scenario_id:
            return
        self.scenarios(case_id)[scenario_id] = scenario
        self._store.upsert_scenario(case_id, scenario_id, scenario)

    def list_scenarios(self, case_id: str) -> list[dict[str, Any]]:
        """케이스에 속하는 시나리오를 생성일 역순으로 반환."""
        items = list(self.scenarios(case_id).values())
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items

    def get_scenario(self, case_id: str, scenario_id: str) -> dict[str, Any] | None:
        """시나리오 1건 조회."""
        return self.scenarios(case_id).get(scenario_id)

    def delete_scenario(self, case_id: str, scenario_id: str) -> bool:
        """시나리오 삭제. 성공하면 True, 없으면 False."""
        bucket = self.scenarios(case_id)
        if scenario_id not in bucket:
            return False
        del bucket[scenario_id]
        self._store.delete_scenario(case_id, scenario_id)
        return True

    # ── 상태 변경 ── #

    def set_scenario_computing(self, case_id: str, scenario_id: str) -> None:
        """비동기 compute 시작 시 상태를 COMPUTING으로 설정 (202 반환 후 백그라운드에서 솔버 실행)."""
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            raise KeyError("scenario not found")
        scenario["status"] = "COMPUTING"
        scenario["started_at"] = _now()
        scenario["failure_reason"] = None
        self._store.upsert_scenario(case_id, scenario_id, scenario)

    def set_scenario_failed(self, case_id: str, scenario_id: str, reason: str) -> None:
        """솔버 타임아웃/실패 시 상태를 FAILED로 설정."""
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            return
        scenario["status"] = "FAILED"
        scenario["completed_at"] = _now()
        scenario["failure_reason"] = reason
        scenario["result"] = None
        self._store.upsert_scenario(case_id, scenario_id, scenario)

    # ── 솔버 실행 ── #

    def run_scenario_solver(self, case_id: str, scenario_id: str) -> dict[str, Any] | None:
        """
        scipy 기반 솔버 실행 (동기). 스레드에서 호출하며 60초 타임아웃 적용.
        성공 시 결과 저장 후 반환, 실패 시 FAILED 저장 후 None 반환.

        리팩토링: 4개의 동일한 except 블록을 하나로 통합.
        """
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            raise KeyError("scenario not found")

        completed_at = _now()
        params = scenario.get("parameters", {})
        constraints = scenario.get("constraints") or []

        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(
                    solve_scenario_result,
                    scenario_id,
                    scenario["scenario_name"],
                    params,
                    constraints,
                    completed_at,
                )
                result = future.result(timeout=SOLVER_TIMEOUT_SECONDS + 5)
        except (SolverInfeasibleError, SolverConvergenceError, SolverTimeoutError, Exception) as e:
            # 모든 솔버 실패를 하나의 블록에서 처리
            self.set_scenario_failed(case_id, scenario_id, str(e))
            return None

        scenario["status"] = "COMPLETED"
        scenario["result"] = result
        scenario["updated_at"] = completed_at
        scenario["completed_at"] = completed_at
        scenario["failure_reason"] = None
        self._store.upsert_scenario(case_id, scenario_id, scenario)
        return result
