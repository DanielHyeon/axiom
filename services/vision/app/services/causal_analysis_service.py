"""
인과 분석 서비스.

VisionRuntime에서 분리된 인과 분석(VAR/Granger) 실행/조회 담당 클래스.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable

from app.engines.causal_analysis_engine import CausalAnalysisEngine
from app.services._utils import utc_now_iso as _now
from app.services.causal_data_fetcher import CausalDataFetcher

logger = logging.getLogger(__name__)


class CausalAnalysisService:
    """
    인과 분석(VAR + Granger + 하이브리드) 실행, 조회, 이력 관리를 담당하는 서비스.

    - engine: 인과 분석 엔진 (기본값 설정)
    - fetcher: 데이터 수집기 (Synapse/Weaver HTTP 호출)
    - id_generator: 고유 ID를 생성하는 콜백 함수
    - causal_results_by_case: 케이스별 인과 분석 결과 메모리 캐시
    """

    def __init__(
        self,
        engine: CausalAnalysisEngine,
        fetcher: CausalDataFetcher,
        id_generator: Callable[[str], str],
        causal_results_by_case: dict[str, dict[str, dict[str, Any]]],
    ) -> None:
        self._engine = engine
        self._fetcher = fetcher
        self._new_id = id_generator
        # 스레드 안전성 — 공유 상태에 Lock 사용
        self._lock = threading.Lock()
        self._results = causal_results_by_case
        # 백그라운드 태스크 참조 보관 — GC에 의한 조기 수거 방지
        self._background_tasks: set[asyncio.Task[None]] = set()

    # ── 분석 실행 ── #

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
        """
        인과 분석 실행 (비동기 + 백그라운드).

        흐름:
        1. 분석 상태 저장소에 RUNNING 상태 등록
        2. 백그라운드 태스크로 데이터 수집 + 엔진 실행
        3. 완료/실패 시 상태 업데이트
        """
        analysis_id = self._new_id("causal-")
        causal_state: dict[str, Any] = {
            "analysis_id": analysis_id,
            "case_id": case_id,
            "target_node_id": target_node_id,
            "target_field": target_field,
            "status": "RUNNING",
            "started_at": _now(),
            "completed_at": None,
            "requested_by": requested_by,
            "edges": [],
            "impact_scores": {},
            "metadata": {},
            "error": None,
        }

        with self._lock:
            self._results.setdefault(case_id, {})[analysis_id] = causal_state

        # 백그라운드 스케줄링 — GC에 의한 조기 수거를 방지하기 위해 참조 보관
        task = asyncio.create_task(
            self._execute_async(
                case_id=case_id,
                analysis_id=analysis_id,
                target_node_id=target_node_id,
                target_field=target_field,
                tenant_id=tenant_id,
                max_lag=max_lag,
                significance_level=significance_level,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return causal_state

    async def _execute_async(
        self,
        case_id: str,
        analysis_id: str,
        target_node_id: str,
        target_field: str,
        tenant_id: str,
        max_lag: int | None,
        significance_level: float | None,
    ) -> None:
        """
        백그라운드 비동기 실행 -- 데이터 수집 + 엔진 실행.
        실패 시 status="FAILED" + error 저장.
        """
        try:
            # (1) 데이터 수집 (비동기 HTTP 호출)
            causal_input = await self._fetcher.fetch(
                case_id=case_id,
                target_node_id=target_node_id,
                target_field=target_field,
                tenant_id=tenant_id,
            )

            # (2) 엔진 실행 (CPU 바운드 -> run_in_executor)
            # significance_level이 요청에서 왔으면 새 엔진 인스턴스 생성
            engine = self._engine
            if significance_level is not None:
                engine = CausalAnalysisEngine(
                    significance_level=significance_level,
                    min_correlation=self._engine.min_correlation,
                    max_lag=max_lag or self._engine.max_lag,
                )

            edges = await asyncio.to_thread(
                engine.analyze,
                data=causal_input.data,
                target_var=causal_input.target_var,
                max_lag=max_lag,
                relation_hints=causal_input.relation_hints,
            )
            impact_scores = engine.calculate_impact_scores(edges)

            # (3) 결과 저장
            edge_dicts = [e.to_dict() for e in edges]
            with self._lock:
                state = self._results.get(case_id, {}).get(analysis_id)
                if state:
                    state["status"] = "COMPLETED"
                    state["completed_at"] = _now()
                    state["edges"] = edge_dicts
                    state["impact_scores"] = impact_scores
                    state["metadata"] = causal_input.node_metadata

            # (4) Synapse에 인과 관계 엣지 저장 (best-effort, 실패해도 계속)
            try:
                saved = await self._fetcher.save_causal_edges_to_synapse(
                    case_id=case_id,
                    edges=edge_dicts,
                    tenant_id=tenant_id,
                    analysis_id=analysis_id,
                )
                logger.info("인과 관계 %d개 Synapse 저장 완료 (analysis=%s)", saved, analysis_id)
            except Exception as e:
                logger.warning("Synapse 인과 관계 저장 실패 (계속 진행): %s", e)

        except Exception as e:
            # 실패 시 status="FAILED" + error 저장
            logger.error("인과 분석 실패 (analysis=%s): %s", analysis_id, e, exc_info=True)
            with self._lock:
                state = self._results.get(case_id, {}).get(analysis_id)
                if state:
                    state["status"] = "FAILED"
                    state["completed_at"] = _now()
                    state["error"] = str(e)

    # ── 조회 ── #

    def get_causal_analysis(self, case_id: str, analysis_id: str) -> dict[str, Any] | None:
        """특정 인과 분석 결과 조회."""
        with self._lock:
            return self._results.get(case_id, {}).get(analysis_id)

    def list_causal_analyses(self, case_id: str) -> list[dict[str, Any]]:
        """케이스별 인과 분석 이력 목록."""
        with self._lock:
            return list(self._results.get(case_id, {}).values())

    def get_latest_causal_edges(self, case_id: str) -> list[dict[str, Any]]:
        """최신 완료된 인과 분석의 엣지 목록 반환 (root_cause_engine 연동용)."""
        with self._lock:
            analyses = list(self._results.get(case_id, {}).values())
        completed = [a for a in analyses if a["status"] == "COMPLETED"]
        if not completed:
            return []
        latest = max(completed, key=lambda a: a.get("completed_at", ""))
        return latest.get("edges", [])
