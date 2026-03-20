"""Event Fork Engine — 이벤트소싱 기반 What-If 시뮬레이션.

BusinessOS 패턴을 Axiom Vision 서비스에 구현:
1. 특정 시점의 온톨로지 상태를 스냅샷 (base_timestamp)
2. 사용자 개입(intervention)을 초기 이벤트로 변환
3. 경량 GWT 룰 평가기를 인프로세스로 실행 (Synapse 크로스서비스 호출 없음)
4. 결과 이벤트 체인을 simulation_events에 기록
5. base vs simulation 상태 비교 (KPI 델타)

기존 DAG Propagation과의 차이:
- DAG: 모델 기반 예측 (비결정적, ML 의존)
- Fork: 이벤트 기반 재생 (결정적, 룰 의존)
- 둘 다 유지하되 사용자가 모드 선택 가능

DB: psycopg2 동기 (Vision 서비스 패턴 준수)
Neo4j: neo4j AsyncDriver (온톨로지 스냅샷 + ActionType 룰 로드)
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.db.pg_utils import _import_psycopg2, _db_url, get_conn_from_pool
from app.engines.whatif_models import InterventionSpec

logger = logging.getLogger("axiom.vision.event_fork")

# ── 보안: 화이트리스트 ─────────────────────────────────────────── #
_ALNUM_UNDERSCORE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_LABELS = {
    "Kpi", "Driver", "Measure", "Process", "Resource",
    "Entity", "ActionType", "Policy",
}

# ── 비교 연산자 매핑 ──────────────────────────────────────────── #
_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
}


# ── 데이터 모델 ───────────────────────────────────────────────── #

@dataclass
class ForkConfig:
    """Event Fork 시뮬레이션 설정."""
    branch_name: str                          # 시나리오 이름
    case_id: str                              # 대상 케이스 ID
    tenant_id: str                            # 테넌트 ID
    base_timestamp: datetime                  # 포크 기준 시점
    interventions: list[InterventionSpec]      # 사용자 개입 목록
    description: str = ""                     # 시나리오 설명
    max_cascade_depth: int = 20               # GWT 체이닝 최대 깊이
    gwt_overrides: dict = field(default_factory=dict)  # 룰 오버라이드
    created_by: str = ""                      # 생성자 ID


@dataclass
class ForkResult:
    """Event Fork 시뮬레이션 결과."""
    branch_id: str
    branch_name: str
    base_state: dict[str, dict[str, Any]]     # 포크 시점 온톨로지 상태
    final_state: dict[str, dict[str, Any]]    # 시뮬레이션 후 상태
    events: list[dict]                         # 발생한 이벤트 체인
    kpi_deltas: dict[str, float]              # KPI별 변화량
    event_count: int                           # 총 이벤트 수
    cascade_depth: int                         # 실제 체이닝 깊이
    converged: bool                            # 수렴 여부 (더 이상 체이닝 없으면 True)

    def to_dict(self) -> dict[str, Any]:
        """API 응답용 JSON 직렬화."""
        return {
            "branch_id": self.branch_id,
            "branch_name": self.branch_name,
            "base_state": self.base_state,
            "final_state": self.final_state,
            "events": self.events,
            "kpi_deltas": self.kpi_deltas,
            "event_count": self.event_count,
            "cascade_depth": self.cascade_depth,
            "converged": self.converged,
        }


# ── 경량 GWT 룰 평가기 (인프로세스) ──────────────────────────── #

@dataclass
class _GWTCondition:
    """Given 조건 하나."""
    type: str               # "state" | "relation"
    node_layer: str = ""
    field_name: str = ""    # 비교할 필드명
    op: str = "=="
    value: Any = None

    @staticmethod
    def from_dict(d: dict) -> _GWTCondition:
        return _GWTCondition(
            type=d.get("type", "state"),
            node_layer=d.get("node_layer", ""),
            field_name=d.get("field", ""),
            op=d.get("op", "=="),
            value=d.get("value"),
        )


@dataclass
class _GWTAction:
    """Then 액션 하나."""
    op: str                 # "SET" | "EMIT" | "EXECUTE"
    target_node: str = ""
    field_name: str = ""
    value: Any = None
    event_type: str = ""
    payload: dict = field(default_factory=dict)
    action_id: str = ""

    @staticmethod
    def from_dict(d: dict) -> _GWTAction:
        return _GWTAction(
            op=d.get("op", "SET"),
            target_node=d.get("target_node", ""),
            field_name=d.get("field", ""),
            value=d.get("value"),
            event_type=d.get("event_type", ""),
            payload=d.get("payload", {}),
            action_id=d.get("action_id", ""),
        )


@dataclass
class _ActionRule:
    """Neo4j에서 로드한 ActionType 노드를 경량 룰로 변환."""
    id: str
    name: str
    case_id: str
    tenant_id: str
    when_event: str
    given: list[_GWTCondition]
    then: list[_GWTAction]
    enabled: bool = True
    priority: int = 100


@dataclass
class _RuleMatchResult:
    """룰 평가 결과."""
    rule_id: str
    rule_name: str
    matched: bool
    state_changes: list[dict] = field(default_factory=list)
    emitted_events: list[dict] = field(default_factory=list)
    chained_actions: list[str] = field(default_factory=list)


class _LightweightGWTEvaluator:
    """경량 GWT 룰 평가기.

    Synapse의 GWTEngine을 크로스서비스 호출 없이 인프로세스로 실행하기 위한 구현.
    ActionType 노드를 Neo4j에서 직접 읽고, given/then을 인메모리로 평가한다.

    dry_run 전용: 실제 Neo4j 쓰기나 이벤트 발행 없이 결과만 반환한다.
    """

    # 룰 캐시 TTL (초) — 300초(5분) 후 자동 만료
    _CACHE_TTL_SECONDS: float = 300.0

    def __init__(self, neo4j_driver) -> None:
        self._driver = neo4j_driver
        # 로드된 룰 캐시 (cache_key → (timestamp, list[_ActionRule]))
        self._rules_cache: dict[str, tuple[float, list[_ActionRule]]] = {}

    async def load_rules(self, case_id: str, tenant_id: str) -> list[_ActionRule]:
        """Neo4j에서 해당 case+tenant의 활성 ActionType 노드를 조회하여 룰로 변환."""
        import time

        cache_key = f"{case_id}:{tenant_id}"
        if cache_key in self._rules_cache:
            cached_at, cached_rules = self._rules_cache[cache_key]
            # TTL 만료 여부 확인 (300초)
            if (time.monotonic() - cached_at) < self._CACHE_TTL_SECONDS:
                return cached_rules
            # TTL 만료 → 캐시 제거 후 재로드
            del self._rules_cache[cache_key]

        query = """
        MATCH (a:ActionType {case_id: $case_id, tenant_id: $tenant_id, enabled: true})
        RETURN a
        ORDER BY a.priority DESC
        """
        rules: list[_ActionRule] = []
        try:
            async with self._driver.session() as session:
                result = await session.run(query, case_id=case_id, tenant_id=tenant_id)
                records = [record async for record in result]

            for record in records:
                node = record["a"]
                props = dict(node)
                # given_conditions / then_actions는 JSON 문자열로 저장됨
                given_raw = json.loads(props.get("given_conditions", "[]"))
                then_raw = json.loads(props.get("then_actions", "[]"))

                rules.append(_ActionRule(
                    id=props.get("id", ""),
                    name=props.get("name", ""),
                    case_id=props.get("case_id", ""),
                    tenant_id=props.get("tenant_id", ""),
                    when_event=props.get("when_event", ""),
                    given=[_GWTCondition.from_dict(c) for c in given_raw],
                    then=[_GWTAction.from_dict(a) for a in then_raw],
                    enabled=props.get("enabled", True),
                    priority=props.get("priority", 100),
                ))

        except Exception:
            logger.warning(
                "ActionType 룰 로드 실패: case=%s, tenant=%s — 룰 없이 시뮬레이션 계속",
                case_id, tenant_id, exc_info=True,
            )

        self._rules_cache[cache_key] = (time.monotonic(), rules)
        return rules

    def evaluate_rule(
        self,
        rule: _ActionRule,
        event_type: str,
        sim_state: dict[str, dict[str, Any]],
        trigger_payload: dict,
    ) -> _RuleMatchResult:
        """단일 룰을 인메모리 상태에 대해 평가한다.

        Given 조건이 모두 만족되면 Then 액션을 sim_state에 적용하고 결과를 반환.
        dry_run 전용이므로 Neo4j 쓰기는 일어나지 않는다.
        """
        # when 이벤트 타입 매칭
        if rule.when_event != event_type:
            return _RuleMatchResult(
                rule_id=rule.id, rule_name=rule.name, matched=False,
            )

        # given 조건 평가
        for cond in rule.given:
            if not self._evaluate_condition(cond, sim_state, trigger_payload):
                return _RuleMatchResult(
                    rule_id=rule.id, rule_name=rule.name, matched=False,
                )

        # then 액션 실행 (인메모리)
        state_changes: list[dict] = []
        emitted_events: list[dict] = []
        chained_actions: list[str] = []

        for action in rule.then:
            if action.op == "SET":
                # 대상 노드 ID 해석 ($trigger.source_node_id → 실제 ID)
                target = self._resolve_target(action.target_node, trigger_payload)
                if target and target in sim_state and action.field_name:
                    old_value = sim_state[target].get(action.field_name)
                    new_value = self._resolve_value(action.value, trigger_payload)
                    sim_state[target][action.field_name] = new_value
                    state_changes.append({
                        "node_id": target,
                        "field": action.field_name,
                        "old_value": old_value,
                        "new_value": new_value,
                    })

            elif action.op == "EMIT":
                # 이벤트 발행 (시뮬레이션 내에서 다음 라운드 트리거로 사용)
                resolved_payload = self._resolve_payload(action.payload, trigger_payload)
                emitted_events.append({
                    "event_type": action.event_type,
                    "payload": resolved_payload,
                })

            elif action.op == "EXECUTE":
                # 다른 ActionType 체이닝
                if action.action_id:
                    chained_actions.append(action.action_id)

        return _RuleMatchResult(
            rule_id=rule.id,
            rule_name=rule.name,
            matched=True,
            state_changes=state_changes,
            emitted_events=emitted_events,
            chained_actions=chained_actions,
        )

    def _evaluate_condition(
        self,
        cond: _GWTCondition,
        sim_state: dict[str, dict[str, Any]],
        trigger_payload: dict,
    ) -> bool:
        """단일 Given 조건을 인메모리 상태에 대해 평가."""
        if cond.type == "state":
            # sim_state에서 해당 계층의 노드들을 검색
            for node_id, props in sim_state.items():
                # node_layer 필터 (빈 문자열이면 모든 노드 대상)
                if cond.node_layer:
                    node_layer = props.get("layer", props.get("label", "")).lower()
                    if node_layer != cond.node_layer.lower():
                        continue
                # 필드 비교
                if cond.field_name and cond.field_name in props:
                    actual = props[cond.field_name]
                    op_fn = _OPS.get(cond.op)
                    if op_fn:
                        try:
                            if op_fn(actual, cond.value):
                                return True
                        except (TypeError, ValueError):
                            continue
            return False

        # relation 타입은 인메모리에서 간소화된 평가만 수행
        # (실제 관계 그래프는 Neo4j에 있으나, 시뮬레이션에서는 상태만 사용)
        return True

    @staticmethod
    def _resolve_target(target_expr: str, trigger_payload: dict) -> str:
        """$trigger.* 변수를 실제 값으로 치환."""
        if not target_expr:
            return ""
        if target_expr.startswith("$trigger."):
            key = target_expr[len("$trigger."):]
            return str(trigger_payload.get(key, target_expr))
        return target_expr

    @staticmethod
    def _resolve_value(value: Any, trigger_payload: dict) -> Any:
        """$trigger.* 변수를 실제 값으로 치환 (값 레벨)."""
        if isinstance(value, str) and value.startswith("$trigger."):
            key = value[len("$trigger."):]
            return trigger_payload.get(key, value)
        return value

    @staticmethod
    def _resolve_payload(payload: dict, trigger_payload: dict) -> dict:
        """페이로드 내 $trigger.* 변수를 치환."""
        resolved = {}
        for k, v in payload.items():
            if isinstance(v, str) and v.startswith("$trigger."):
                key = v[len("$trigger."):]
                resolved[k] = trigger_payload.get(key, v)
            else:
                resolved[k] = v
        return resolved


# ── Event Fork Engine ─────────────────────────────────────────── #

class EventForkEngine:
    """이벤트 포크 기반 What-If 시뮬레이션 엔진.

    Major #5 준수: GWT 룰을 dry_run 모드로 실행하여
    시뮬레이션 중 실제 Neo4j 변경이나 이벤트 발행이 일어나지 않는다.
    모든 상태 변경은 인메모리 sim_state에만 적용된다.
    """

    def __init__(self, neo4j_driver, db_url: str | None = None) -> None:
        """
        Args:
            neo4j_driver: neo4j.AsyncDriver 인스턴스 (온톨로지 스냅샷 + ActionType 로드)
            db_url: PostgreSQL 접속 URL (None이면 환경변수에서 자동 로드)
        """
        self._driver = neo4j_driver
        self._db_url = db_url
        # 경량 GWT 평가기 (인프로세스)
        self._gwt_evaluator = _LightweightGWTEvaluator(neo4j_driver)

    def _get_db_url(self) -> str:
        """psycopg2용 PostgreSQL URL을 반환."""
        if self._db_url:
            url = self._db_url
        else:
            return _db_url()
        if url.startswith("postgresql+asyncpg://"):
            return "postgresql://" + url[len("postgresql+asyncpg://"):]
        return url

    # ── 공개 API ──────────────────────────────────────────────── #

    async def create_fork(self, config: ForkConfig) -> str:
        """시뮬레이션 브랜치를 생성하고 branch_id를 반환한다.

        PostgreSQL vision.simulation_branches 테이블에 INSERT.
        psycopg2 블로킹 호출을 asyncio.to_thread로 래핑.
        """
        branch_id = f"sim_branch_{uuid.uuid4().hex[:12]}"

        interventions_json = json.dumps(
            [iv.to_dict() for iv in config.interventions], ensure_ascii=False,
        )
        overrides_json = json.dumps(config.gwt_overrides, ensure_ascii=False)

        def _insert():
            with get_conn_from_pool() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO vision.simulation_branches
                        (id, case_id, tenant_id, name, description,
                         base_timestamp, status, interventions,
                         gwt_overrides, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, 'created', %s, %s, %s)
                    """,
                    (
                        branch_id,
                        config.case_id,
                        config.tenant_id,
                        config.branch_name,
                        config.description or None,
                        config.base_timestamp,
                        interventions_json,
                        overrides_json,
                        config.created_by or None,
                    ),
                )
                cur.close()
                conn.commit()

        await asyncio.to_thread(_insert)
        logger.info("시뮬레이션 브랜치 생성: %s (case=%s)", branch_id, config.case_id)
        return branch_id

    async def run_simulation(self, branch_id: str) -> ForkResult:
        """시뮬레이션을 실행하고 결과를 반환한다.

        1. 브랜치 정보 로드
        2. base_timestamp 시점의 온톨로지 상태 스냅샷
        3. intervention → 초기 이벤트 변환 + sim_state 적용
        4. GWT 룰 체인 실행 (인프로세스 dry_run)
        5. KPI 델타 계산
        6. 결과 저장 (simulation_events + branch 업데이트)
        """
        # 브랜치 상태를 running으로 변경
        await self._update_branch_status(branch_id, "running")

        try:
            # 1. 브랜치 정보 로드
            branch = await self._load_branch(branch_id)
            case_id = branch["case_id"]
            tenant_id = branch["tenant_id"]

            # 2. 기준 상태 스냅샷 (Major #11: OntologySnapshot 폴백 포함)
            base_timestamp = branch["base_timestamp"]
            if isinstance(base_timestamp, str):
                base_timestamp = datetime.fromisoformat(base_timestamp)
            base_state = await self._snapshot_ontology_state(case_id, base_timestamp, tenant_id)

            # 3. 시뮬레이션 상태 = 기준 상태 깊은 복사 (중첩 dict/list 안전)
            sim_state: dict[str, dict[str, Any]] = copy.deepcopy(base_state)

            # intervention 파싱
            interventions_raw = branch["interventions"]
            if isinstance(interventions_raw, str):
                interventions_raw = json.loads(interventions_raw)
            interventions = [InterventionSpec(**iv) for iv in interventions_raw]

            # GWT 오버라이드 파싱
            gwt_overrides = branch.get("gwt_overrides", {})
            if isinstance(gwt_overrides, str):
                gwt_overrides = json.loads(gwt_overrides)

            # 4. intervention을 초기 이벤트로 변환
            events: list[dict] = []
            seq = 0

            for intervention in interventions:
                # sim_state에 개입 적용
                if intervention.node_id in sim_state:
                    sim_state[intervention.node_id][intervention.field] = intervention.value
                else:
                    # 노드가 없으면 새로 생성
                    sim_state[intervention.node_id] = {intervention.field: intervention.value}

                event = {
                    "id": f"sim_evt_{uuid.uuid4().hex[:12]}",
                    "event_type": "INTERVENTION_APPLIED",
                    "aggregate_type": "OntologyNode",
                    "aggregate_id": intervention.node_id,
                    "payload": intervention.to_dict(),
                    "source": "intervention",
                    "source_rule_id": None,
                    "sequence": seq,
                    "state_snapshot": json.dumps(
                        {intervention.node_id: sim_state.get(intervention.node_id, {})},
                        ensure_ascii=False,
                    ),
                }
                events.append(event)
                seq += 1

            # 5. GWT 룰 체인 실행 (경량 인프로세스 평가기)
            max_depth = 20
            if isinstance(branch.get("interventions"), str):
                # max_cascade_depth는 ForkConfig에만 있고 DB에 저장하지 않으므로 기본값 사용
                pass

            rules = await self._gwt_evaluator.load_rules(case_id, tenant_id)
            depth = 0
            pending_events = list(events)

            while pending_events and depth < max_depth:
                next_events: list[dict] = []

                for evt in pending_events:
                    for rule in rules:
                        result = self._gwt_evaluator.evaluate_rule(
                            rule=rule,
                            event_type=evt["event_type"],
                            sim_state=sim_state,
                            trigger_payload=evt.get("payload", {}),
                        )
                        if not result.matched:
                            continue

                        # 상태 변경은 evaluate_rule 내부에서 이미 sim_state에 적용됨
                        # 발행된 이벤트를 다음 라운드 트리거로 추가
                        for emitted in result.emitted_events:
                            cascade_event = {
                                "id": f"sim_evt_{uuid.uuid4().hex[:12]}",
                                "event_type": emitted["event_type"],
                                "aggregate_type": "ActionType",
                                "aggregate_id": result.rule_id,
                                "payload": emitted.get("payload", {}),
                                "source": "gwt_rule",
                                "source_rule_id": result.rule_id,
                                "sequence": seq,
                                "state_snapshot": None,
                            }
                            next_events.append(cascade_event)
                            events.append(cascade_event)
                            seq += 1

                        # 체이닝된 액션도 다음 라운드 이벤트로 변환
                        for chained_id in result.chained_actions:
                            chain_event = {
                                "id": f"sim_evt_{uuid.uuid4().hex[:12]}",
                                "event_type": f"EXECUTE_{chained_id}",
                                "aggregate_type": "ActionType",
                                "aggregate_id": chained_id,
                                "payload": {"chained_from": result.rule_id},
                                "source": "cascade",
                                "source_rule_id": result.rule_id,
                                "sequence": seq,
                                "state_snapshot": None,
                            }
                            next_events.append(chain_event)
                            events.append(chain_event)
                            seq += 1

                pending_events = next_events
                depth += 1

            # 6. KPI 델타 계산
            kpi_deltas = self._calculate_kpi_deltas(base_state, sim_state)

            # 7. 결과를 PostgreSQL에 저장
            await self._save_simulation_events(branch_id, events)
            await self._update_branch_result(
                branch_id, kpi_deltas, len(events), depth,
            )

            fork_result = ForkResult(
                branch_id=branch_id,
                branch_name=branch["name"],
                base_state=base_state,
                final_state=sim_state,
                events=events,
                kpi_deltas=kpi_deltas,
                event_count=len(events),
                cascade_depth=depth,
                converged=len(pending_events) == 0,
            )

            logger.info(
                "시뮬레이션 완료: branch=%s, events=%d, depth=%d, converged=%s",
                branch_id, len(events), depth, fork_result.converged,
            )
            return fork_result

        except Exception:
            # 실패 시 브랜치 상태를 failed로 변경
            await self._update_branch_status(branch_id, "failed")
            logger.exception("시뮬레이션 실패: branch=%s", branch_id)
            raise

    async def compare_scenarios(self, branch_ids: list[str]) -> dict[str, Any]:
        """여러 시뮬레이션 브랜치의 결과를 비교하는 매트릭스를 생성한다.

        Returns:
            {
                "scenarios": {branch_id: {name, kpi_deltas, event_count}},
                "comparison_matrix": {kpi_key: {branch_id: delta}},
            }
        """
        scenarios: dict[str, dict] = {}

        def _load_all():
            """모든 브랜치 결과를 한 번에 로드 (커넥션 풀 사용)."""
            psycopg2 = _import_psycopg2()
            from psycopg2.extras import RealDictCursor
            with get_conn_from_pool() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                for bid in branch_ids:
                    cur.execute(
                        """
                        SELECT name, result_summary, event_count, status
                        FROM vision.simulation_branches
                        WHERE id = %s
                        """,
                        (bid,),
                    )
                    row = cur.fetchone()
                    if row:
                        summary = row["result_summary"]
                        if isinstance(summary, str):
                            summary = json.loads(summary)
                        scenarios[bid] = {
                            "name": row["name"],
                            "status": row["status"],
                            "kpi_deltas": summary or {},
                            "event_count": row["event_count"] or 0,
                        }
                cur.close()

        await asyncio.to_thread(_load_all)

        # KPI별 시나리오 비교 매트릭스 생성
        all_kpis: set[str] = set()
        for s in scenarios.values():
            all_kpis.update(s["kpi_deltas"].keys())

        comparison_matrix: dict[str, dict[str, float]] = {}
        for kpi in sorted(all_kpis):
            comparison_matrix[kpi] = {
                bid: s["kpi_deltas"].get(kpi, 0.0)
                for bid, s in scenarios.items()
            }

        return {
            "scenarios": scenarios,
            "comparison_matrix": comparison_matrix,
        }

    # ── 내부 헬퍼 메서드 ──────────────────────────────────────── #

    @staticmethod
    def _calculate_kpi_deltas(
        base_state: dict[str, dict[str, Any]],
        sim_state: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        """base_state와 sim_state 사이의 수치 변화량을 계산한다."""
        kpi_deltas: dict[str, float] = {}
        for node_id, state in sim_state.items():
            if node_id not in base_state:
                continue
            for field_name, new_val in state.items():
                old_val = base_state[node_id].get(field_name)
                if isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
                    delta = new_val - old_val
                    if abs(delta) > 1e-6:
                        kpi_deltas[f"{node_id}::{field_name}"] = round(delta, 6)
        return kpi_deltas

    async def _snapshot_ontology_state(
        self, case_id: str, timestamp: datetime, tenant_id: str = "",
    ) -> dict[str, dict[str, Any]]:
        """온톨로지 상태 스냅샷.

        Major #11 준수:
        1. OntologySnapshot 노드가 존재하면 base_timestamp 이전 가장 가까운 스냅샷 사용
        2. 스냅샷 없으면 현재 그래프 상태를 기준으로 사용 (폴백)
        """
        # 1차: OntologySnapshot에서 가장 가까운 스냅샷 조회
        snapshot_query = """
        MATCH (s:OntologySnapshot {case_id: $case_id, tenant_id: $tenant_id})
        WHERE s.created_at <= $timestamp
        RETURN s.data AS data, s.created_at AS ts
        ORDER BY s.created_at DESC
        LIMIT 1
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    snapshot_query,
                    case_id=case_id,
                    tenant_id=tenant_id,
                    timestamp=timestamp.isoformat(),
                )
                records = [record async for record in result]

            if records and records[0].get("data"):
                data = records[0]["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                logger.info(
                    "OntologySnapshot 로드 성공: case=%s, snapshot_ts=%s",
                    case_id, records[0].get("ts"),
                )
                return data
        except Exception:
            logger.warning(
                "OntologySnapshot 조회 실패, 현재 상태로 폴백: case=%s",
                case_id, exc_info=True,
            )

        # 2차: 스냅샷 없으면 현재 그래프 상태 사용 (폴백)
        logger.warning(
            "OntologySnapshot 없음, 현재 상태를 기준으로 시뮬레이션: case=%s, ts=%s",
            case_id, timestamp,
        )
        fallback_query = """
        MATCH (n {case_id: $case_id, tenant_id: $tenant_id})
        WHERE n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource
        RETURN n.node_id AS id, properties(n) AS props
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    fallback_query, case_id=case_id, tenant_id=tenant_id,
                )
                records = [record async for record in result]
            return {r["id"]: dict(r["props"]) for r in records if r.get("id")}
        except Exception:
            logger.warning(
                "온톨로지 그래프 조회 실패, 빈 상태로 시뮬레이션: case=%s",
                case_id, exc_info=True,
            )
            return {}

    async def _load_branch(self, branch_id: str) -> dict:
        """브랜치 정보를 PostgreSQL에서 로드한다."""
        def _query():
            psycopg2 = _import_psycopg2()
            from psycopg2.extras import RealDictCursor
            with get_conn_from_pool() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(
                    "SELECT * FROM vision.simulation_branches WHERE id = %s",
                    (branch_id,),
                )
                row = cur.fetchone()
                cur.close()
                if not row:
                    raise ValueError(f"브랜치를 찾을 수 없음: {branch_id}")
                return dict(row)

        return await asyncio.to_thread(_query)

    async def _update_branch_status(self, branch_id: str, status: str) -> None:
        """브랜치 상태를 업데이트한다."""
        def _update():
            with get_conn_from_pool() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE vision.simulation_branches SET status = %s WHERE id = %s",
                    (status, branch_id),
                )
                cur.close()
                conn.commit()

        await asyncio.to_thread(_update)

    async def _save_simulation_events(self, branch_id: str, events: list[dict]) -> None:
        """시뮬레이션 이벤트를 PostgreSQL에 배치 저장한다."""
        if not events:
            return

        def _batch_insert():
            with get_conn_from_pool() as conn:
                cur = conn.cursor()
                for event in events:
                    payload = event.get("payload", {})
                    if isinstance(payload, dict):
                        payload = json.dumps(payload, ensure_ascii=False)
                    state_snap = event.get("state_snapshot")
                    if isinstance(state_snap, dict):
                        state_snap = json.dumps(state_snap, ensure_ascii=False)

                    cur.execute(
                        """
                        INSERT INTO vision.simulation_events
                            (id, branch_id, sequence_number, event_type,
                             aggregate_type, aggregate_id, payload,
                             source, source_rule_id, state_snapshot)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event.get("id", f"sim_evt_{uuid.uuid4().hex[:12]}"),
                            branch_id,
                            event["sequence"],
                            event["event_type"],
                            event.get("aggregate_type"),
                            event.get("aggregate_id", ""),
                            payload,
                            event.get("source", "unknown"),
                            event.get("source_rule_id"),
                            state_snap,
                        ),
                    )
                cur.close()
                conn.commit()

        await asyncio.to_thread(_batch_insert)
        logger.debug("시뮬레이션 이벤트 저장: branch=%s, count=%d", branch_id, len(events))

    async def _update_branch_result(
        self,
        branch_id: str,
        kpi_deltas: dict[str, float],
        event_count: int,
        depth: int,
    ) -> None:
        """시뮬레이션 완료 후 브랜치 결과 요약을 업데이트한다."""
        summary_json = json.dumps(kpi_deltas, ensure_ascii=False)

        def _update():
            with get_conn_from_pool() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE vision.simulation_branches
                    SET status = 'completed',
                        result_summary = %s,
                        event_count = %s,
                        completed_at = now()
                    WHERE id = %s
                    """,
                    (summary_json, event_count, branch_id),
                )
                cur.close()
                conn.commit()

        await asyncio.to_thread(_update)
