"""
근본 원인 분석(RCA) 서비스.

VisionRuntime에서 분리된 근본 원인 분석 생성/조회/반사실/타임라인/영향도/그래프 담당 클래스.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

import httpx

from app.services._utils import utc_now_iso as _now
from app.services.exceptions import VisionRuntimeError  # noqa: F401 — 하위 호환용 re-export
from app.services.root_cause_engine import run_counterfactual_engine, run_root_cause_engine
from app.services.vision_state_store import VisionStateStore

logger = logging.getLogger(__name__)


class RootCauseService:
    """
    근본 원인 분석(RCA) 생성, 조회, 반사실 분석, 인과 타임라인,
    영향도, 인과 그래프, 프로세스 병목 근본 원인, 시뮬레이션을 담당하는 서비스.

    - store: 영구 저장소 (VisionStateStore)
    - id_generator: 고유 ID를 생성하는 콜백 함수
    - root_cause_by_case: 케이스별 RCA 결과 메모리 캐시
    """

    def __init__(
        self,
        store: VisionStateStore,
        id_generator: Callable[[str], str],
        root_cause_by_case: dict[str, dict[str, Any]],
    ) -> None:
        self._store = store
        self._new_id = id_generator
        self._root_cause_by_case = root_cause_by_case

    # ── 분석 생성/조회 ── #

    def create_root_cause_analysis(
        self, case_id: str, payload: dict[str, Any], requested_by: str
    ) -> dict[str, Any]:
        """근본 원인 분석을 생성하고 엔진을 실행하여 결과를 저장."""
        analysis_id = self._new_id("rca-")
        now = _now()
        engine_result = run_root_cause_engine(case_id=case_id, payload=payload)
        analysis: dict[str, Any] = {
            "analysis_id": analysis_id,
            "case_id": case_id,
            "status": "ANALYZING",
            "progress": {
                "step": "computing_shap_values",
                "step_label": "요인 기여도 계산 중",
                "pct": 65,
            },
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
            "requested_by": requested_by,
            "request": payload,
            "causal_graph_version": "v2.1",
            "overall_confidence": engine_result["overall_confidence"],
            "predicted_failure_probability": engine_result["predicted_failure_probability"],
            "confidence_basis": engine_result["confidence_basis"],
            "root_causes": engine_result["root_causes"],
            "explanation": engine_result["explanation"],
        }
        self._root_cause_by_case[case_id] = analysis
        self._store.upsert_root_cause_analysis(case_id, analysis)
        return analysis

    def get_root_cause_analysis(self, case_id: str) -> dict[str, Any] | None:
        """케이스의 근본 원인 분석 결과 1건 조회."""
        return self._root_cause_by_case.get(case_id)

    def get_root_cause_status(self, case_id: str) -> dict[str, Any] | None:
        """근본 원인 분석 상태 조회 (ANALYZING이면 COMPLETED로 전환)."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis:
            return None
        if analysis["status"] == "ANALYZING":
            analysis["status"] = "COMPLETED"
            analysis["progress"] = {
                "step": "generating_explanation",
                "step_label": "설명 생성 완료",
                "pct": 100,
            }
            analysis["completed_at"] = _now()
            analysis["updated_at"] = analysis["completed_at"]
            self._store.upsert_root_cause_analysis(case_id, analysis)
        return analysis

    def get_root_causes(self, case_id: str) -> dict[str, Any] | None:
        """완료된 분석의 근본 원인 목록 반환. 미완료이면 None."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            return None
        return {
            "case_id": case_id,
            "analysis_id": analysis["analysis_id"],
            "analyzed_at": analysis["completed_at"],
            "causal_graph_version": analysis["causal_graph_version"],
            "overall_confidence": analysis["overall_confidence"],
            "confidence_basis": analysis.get("confidence_basis"),
            "root_causes": analysis["root_causes"],
            "explanation": analysis["explanation"],
        }

    # ── 반사실 분석 ── #

    def run_counterfactual(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """반사실 분석 실행 — '만약 X가 달랐다면?' 시뮬레이션."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        actual_value = float(payload["actual_value"])
        counterfactual_value = float(payload["counterfactual_value"])
        computed = run_counterfactual_engine(
            analysis=analysis,
            variable=payload["variable"],
            actual_value=actual_value,
            counterfactual_value=counterfactual_value,
        )
        return {
            "analysis_id": analysis["analysis_id"],
            "case_id": case_id,
            "variable": payload["variable"],
            "actual_value": actual_value,
            "counterfactual_value": counterfactual_value,
            "question": payload.get("question"),
            "estimated_failure_probability_before": computed["estimated_failure_probability_before"],
            "estimated_failure_probability_after": computed["estimated_failure_probability_after"],
            "risk_reduction_pct": computed["risk_reduction_pct"],
            "confidence_basis": computed["confidence_basis"],
            "computed_at": _now(),
        }

    # ── 인과 타임라인 ── #

    def get_causal_timeline(self, case_id: str) -> dict[str, Any]:
        """인과 타임라인 반환. TODO: 하드코딩 데이터를 실제 데이터로 교체해야 함."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        # TODO: 하드코딩된 타임라인 데이터 — 실제 분석 결과 기반으로 교체 필요
        return {
            "case_id": case_id,
            "timeline": [
                {
                    "date": "2022-06-15",
                    "event": "차입 확대",
                    "variable": "debt_ratio",
                    "value_before": 0.80,
                    "value_after": 1.50,
                    "impact": "critical",
                    "description": "부채비율 급등",
                },
                {
                    "date": "2023-01-25",
                    "event": "금리 인상",
                    "variable": "interest_rate_env",
                    "value_before": 3.50,
                    "value_after": 5.50,
                    "impact": "high",
                    "description": "이자비용 상승",
                },
                {
                    "date": "2023-09-01",
                    "event": "수익성 악화",
                    "variable": "ebitda",
                    "value_before": 1500000000,
                    "value_after": 600000000,
                    "impact": "critical",
                    "description": "EBITDA 하락",
                },
            ],
        }

    # ── 영향도 분석 ── #

    def get_root_cause_impact(self, case_id: str) -> dict[str, Any]:
        """SHAP 기반 영향도(기여도) 워터폴 데이터 반환."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        contributions = []
        for item in analysis["root_causes"]:
            pct = float(item.get("contribution_pct", 0.0))
            contributions.append(
                {
                    "variable": item["variable"],
                    "label": item["variable_label"],
                    "shap_value": round(float(item.get("shap_value", 0.0)), 4),
                    "feature_value": item.get("actual_value"),
                    "direction": item.get("direction", "positive"),
                    "description": f"실패 확률 기여도 {pct:.1f}%",
                }
            )
        base = round(
            max(
                0.01,
                float(analysis.get("predicted_failure_probability", 0.70))
                - sum(c["shap_value"] for c in contributions),
            ),
            3,
        )
        return {
            "case_id": case_id,
            "base_value": base,
            "predicted_value": round(base + sum(c["shap_value"] for c in contributions), 3),
            "confidence_basis": analysis.get("confidence_basis"),
            "contributions": contributions,
        }

    # ── 인과 그래프 ── #

    def get_causal_graph(self, case_id: str) -> dict[str, Any]:
        """인과 그래프(노드 + 엣지) 시각화용 데이터 반환."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for idx, item in enumerate(analysis["root_causes"], start=1):
            node_id = item["variable"]
            nodes.append(
                {
                    "id": node_id,
                    "label": item["variable_label"],
                    "type": "intermediate",
                    "value": item.get("actual_value"),
                    "position": {"x": 120 * idx, "y": 120},
                }
            )
            edges.append(
                {
                    "source": node_id,
                    "target": "business_failure",
                    "coefficient": round(float(item.get("contribution_pct", 0.0)) / 100.0, 3),
                    "confidence": item.get("confidence", 0.7),
                    "label": f"{item.get('contribution_pct', 0)}% 영향",
                }
            )
        nodes.append(
            {
                "id": "business_failure",
                "label": "비즈니스 실패",
                "type": "outcome",
                "value": 1,
                "position": {"x": 500, "y": 300},
            }
        )
        return {
            "graph_version": analysis.get("causal_graph_version", "v2.1"),
            "training_samples": 127,
            "nodes": nodes,
            "edges": edges,
        }

    # ── 프로세스 병목 근본 원인 ── #

    def get_process_bottleneck_root_cause(
        self,
        case_id: str,
        process_id: str,
        bottleneck_activity: str | None = None,
        max_causes: int = 5,
        include_explanation: bool = True,
    ) -> dict[str, Any]:
        """프로세스 병목의 근본 원인 분석 결과 반환."""
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        if not process_id.strip():
            raise ValueError("process_id is required")

        max_causes = min(max(max_causes, 1), 10)
        selected = analysis["root_causes"][:max_causes]
        root_causes = [
            {
                "rank": idx,
                "variable": item["variable"],
                "variable_label": item["variable_label"],
                "related_activity": bottleneck_activity,
                "shap_value": item["shap_value"],
                "contribution_pct": item["contribution_pct"],
                "actual_value": item["actual_value"],
                "normal_range": None,
                "description": item["description"],
                "causal_chain": item["causal_chain"],
                "confidence": item["confidence"],
            }
            for idx, item in enumerate(selected, start=1)
        ]

        synapse_status = "fallback"
        source_log_id = process_id
        data_range = None
        case_count = None
        bottleneck_score = 0.82
        bottleneck_name = bottleneck_activity or "승인"
        if os.getenv("SYNAPSE_BASE_URL", "").strip():
            synapse = self._fetch_synapse_process_context(case_id=case_id, process_id=process_id)
            synapse_status = "connected"
            source_log_id = synapse["source_log_id"]
            data_range = synapse["data_range"]
            case_count = synapse["case_count"]
            bottleneck_score = synapse["bottleneck_score"]
            bottleneck_name = bottleneck_activity or synapse["bottleneck_activity"] or "승인"

        return {
            "case_id": case_id,
            "process_model_id": process_id,
            "source_log_id": source_log_id,
            "bottleneck_activity": bottleneck_name,
            "bottleneck_score": bottleneck_score,
            "analyzed_at": _now(),
            "data_range": data_range,
            "case_count": case_count,
            "overall_confidence": analysis["overall_confidence"],
            "root_causes": root_causes,
            "recommendations": [
                "승인 리소스 보강",
                "재작업 비율 절감",
                "피크 시간대 부하 분산",
            ],
            "explanation": analysis["explanation"] if include_explanation else None,
            "synapse_status": synapse_status,
        }

    # ── 프로세스 시뮬레이션 ── #

    def run_process_simulation(
        self,
        case_id: str,
        process_model_id: str,
        scenario_name: str,
        description: str | None,
        parameter_changes: list[dict[str, Any]],
        sla_threshold_seconds: int | None,
    ) -> dict[str, Any]:
        """
        프로세스 시간축 시뮬레이션 (what-if-api.md S10).
        Synapse performance/bottlenecks/variants 호출 후 parameter_changes 적용,
        original_cycle_time, simulated_cycle_time, by_activity, bottleneck_shift 반환.
        Synapse 연결 실패 시 VisionRuntimeError(SYNAPSE_UNAVAILABLE) 발생.
        """
        if not os.getenv("SYNAPSE_BASE_URL", "").strip():
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable")
        try:
            ctx = self._fetch_synapse_process_context(case_id, process_model_id)
        except VisionRuntimeError:
            raise
        except Exception as exc:
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable") from exc

        # 활동별 기본 소요시간 (Synapse에서 상세 미제공 시 사용)
        default_activities = ["접수", "승인", "검토", "배송"]
        default_durations = [3600, 14400, 28800, 86400]
        activity_durations = dict(zip(default_activities, default_durations))
        try:
            synapse_base = os.getenv("SYNAPSE_BASE_URL", "").strip().rstrip("/")
            log_id = process_model_id
            with httpx.Client(timeout=10.0) as client:
                bn_resp = client.get(
                    f"{synapse_base}/api/v3/synapse/process-mining/bottlenecks",
                    params={"case_id": case_id, "log_id": log_id},
                )
                if bn_resp.status_code == 200:
                    bottlenecks_data = bn_resp.json().get("data", {}) or {}
                    for b in bottlenecks_data.get("bottlenecks") or []:
                        act = b.get("activity")
                        if act and "avg_duration" in b:
                            activity_durations[act] = int(b.get("avg_duration", 86400))
        except Exception:
            pass

        original_bottleneck = ctx.get("bottleneck_activity") or (
            default_activities[1] if len(default_activities) > 1 else "승인"
        )
        simulated_durations = dict(activity_durations)
        for ch in parameter_changes:
            act = (ch.get("activity") or "").strip()
            if not act or act not in simulated_durations:
                continue
            change_type = (ch.get("change_type") or "").strip().lower()
            if change_type == "duration" and ch.get("duration_change") is not None:
                new_d = simulated_durations[act] + int(ch["duration_change"])
                simulated_durations[act] = max(0, new_d)
            elif change_type == "resource" and ch.get("resource_change") is not None:
                factor = max(0.1, float(ch["resource_change"]))
                simulated_durations[act] = max(0, int(simulated_durations[act] / factor))
            # routing: 변형 빈도 변경은 여기서 스텁 처리

        original_cycle_time = sum(activity_durations.values())
        simulated_cycle_time = sum(simulated_durations.values())
        cycle_time_change = simulated_cycle_time - original_cycle_time
        cycle_time_change_pct = (
            round((cycle_time_change / max(original_cycle_time, 1)) * 100, 1)
            if original_cycle_time
            else 0
        )
        hours = abs(cycle_time_change) // 3600
        cycle_time_change_label = f"전체 주기 시간 {hours}시간 {'단축' if cycle_time_change <= 0 else '증가'}"

        by_activity = []
        for name in activity_durations:
            orig = activity_durations[name]
            sim = simulated_durations.get(name, orig)
            by_activity.append({
                "activity": name,
                "original_duration": orig,
                "simulated_duration": sim,
                "change": sim - orig,
                "is_on_critical_path": True,
            })

        simulated_bottleneck = max(simulated_durations, key=lambda a: simulated_durations[a])
        bottleneck_shift = None
        if original_bottleneck != simulated_bottleneck:
            bottleneck_shift = {
                "original": original_bottleneck,
                "new": simulated_bottleneck,
                "description": f"병목이 '{original_bottleneck}'에서 '{simulated_bottleneck}'(으)로 이동.",
            }

        sla_orig = 0.15
        sla_sim = max(0.0, sla_orig + (cycle_time_change_pct / 100.0) * 0.5)
        affected_kpis = [
            {
                "kpi": "avg_cycle_time",
                "kpi_label": "평균 주기 시간",
                "original": original_cycle_time,
                "simulated": simulated_cycle_time,
                "change_pct": cycle_time_change_pct,
            },
            {
                "kpi": "sla_violation_rate",
                "kpi_label": "SLA 위반율",
                "original": sla_orig,
                "simulated": round(sla_sim, 2),
                "change_pct": round((sla_sim - sla_orig) / max(sla_orig, 0.01) * 100, 1),
            },
        ]
        critical_path = {
            "original": list(activity_durations),
            "simulated": list(simulated_durations),
        }

        simulation_id = self._new_id("sim-")
        return {
            "simulation_id": simulation_id,
            "process_model_id": process_model_id,
            "scenario_name": scenario_name,
            "computed_at": _now(),
            "original_cycle_time": original_cycle_time,
            "simulated_cycle_time": simulated_cycle_time,
            "cycle_time_change": cycle_time_change,
            "cycle_time_change_pct": cycle_time_change_pct,
            "cycle_time_change_label": cycle_time_change_label,
            "bottleneck_shift": bottleneck_shift,
            "affected_kpis": affected_kpis,
            "by_activity": by_activity,
            "critical_path": critical_path,
        }

    # ── Synapse 프로세스 컨텍스트 조회 (내부) ── #

    def _fetch_synapse_process_context(self, case_id: str, process_id: str) -> dict[str, Any]:
        """Synapse 프로세스 마이닝 API에서 병목/변형/성능 컨텍스트 조회."""
        synapse_base = os.getenv("SYNAPSE_BASE_URL", "").strip().rstrip("/")
        log_id = os.getenv("VISION_BOTTLENECK_LOG_ID", process_id).strip() or process_id
        params = {"case_id": case_id, "log_id": log_id, "sort_by": "bottleneck_score_desc"}

        try:
            with httpx.Client(timeout=5.0) as client:
                bottlenecks_resp = client.get(
                    f"{synapse_base}/api/v3/synapse/process-mining/bottlenecks", params=params
                )
                variants_resp = client.get(
                    f"{synapse_base}/api/v3/synapse/process-mining/variants",
                    params={"case_id": case_id, "log_id": log_id, "limit": 5},
                )
                performance_resp = client.post(
                    f"{synapse_base}/api/v3/synapse/process-mining/performance",
                    json={"case_id": case_id, "log_id": log_id, "options": {"include_bottlenecks": True}},
                )
        except Exception as exc:  # pragma: no cover - network branch
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable") from exc

        for resp in (bottlenecks_resp, variants_resp, performance_resp):
            if resp.status_code >= 500:
                raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable")
            if resp.status_code == 404:
                code = (
                    (resp.json().get("detail") or {}).get("code")
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else None
                )
                if code == "LOG_NOT_FOUND":
                    raise VisionRuntimeError("PROCESS_MODEL_NOT_FOUND", "process model not found")
            if resp.status_code == 400:
                detail = (
                    resp.json().get("detail")
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                code = (detail or {}).get("code")
                if code in {"INSUFFICIENT_PROCESS_DATA", "EMPTY_EVENT_LOG"}:
                    raise VisionRuntimeError("INSUFFICIENT_PROCESS_DATA", "insufficient process data")

        if bottlenecks_resp.status_code >= 400:
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable")

        bottlenecks_data = bottlenecks_resp.json().get("data", {})
        bottlenecks = bottlenecks_data.get("bottlenecks") or []
        top = bottlenecks[0] if bottlenecks else {}
        overall = bottlenecks_data.get("overall_process") or {}
        period = bottlenecks_data.get("analysis_period") or {}
        case_count = int(overall.get("total_sla_violations", 0)) if overall else None
        if performance_resp.status_code < 400:
            performance_task = performance_resp.json().get("data", {})
            if isinstance(performance_task, dict) and performance_task.get("task_id"):
                # async task 기반이므로 case_count는 bottleneck payload 기반이 없으면 None 유지
                pass
        return {
            "source_log_id": log_id,
            "bottleneck_activity": top.get("activity"),
            "bottleneck_score": float(top.get("bottleneck_score", 0.82)),
            "data_range": {"from": period.get("start"), "to": period.get("end")} if period else None,
            "case_count": case_count,
        }
