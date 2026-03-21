"""What-if 위자드 서비스 단위 테스트.

대상 모듈: app.services.whatif_wizard_service
순수 함수 및 async 함수만 테스트 (DB/Neo4j 의존 없음).
"""
from __future__ import annotations

import pytest
import numpy as np

from app.services.whatif_wizard_service import (
    EdgeCandidate,
    EdgeMethod,
    SimulationNode,
    WhatIfScenario,
    discover_edges,
    compute_correlation_matrix,
    build_model_graph,
    train_models,
    validate_models,
    simulate,
    compare_scenarios,
    _topological_sort,
    _has_cycle,
)


# ===================================================================
# 헬퍼: 테스트용 데이터 생성
# ===================================================================

def _make_correlated_data(n: int = 50, noise: float = 0.1, seed: int = 42) -> dict[str, list[float]]:
    """A와 B가 높은 상관관계를 갖는 테스트 데이터 생성."""
    rng = np.random.default_rng(seed)
    a = np.linspace(0, 10, n) + rng.normal(0, noise, n)
    b = 2.0 * a + 3.0 + rng.normal(0, noise, n)
    c = rng.normal(0, 1, n)  # A, B와 무관한 노이즈
    return {"A": a.tolist(), "B": b.tolist(), "C": c.tolist()}


def _make_graph_abc() -> dict[str, SimulationNode]:
    """A -> B -> C 선형 체인 그래프."""
    return {
        "A": SimulationNode(variable="A"),
        "B": SimulationNode(variable="B", parents=["A"]),
        "C": SimulationNode(variable="C", parents=["B"]),
    }


# ===================================================================
# Step 1: 엣지 탐색 (discover_edges)
# ===================================================================

class TestDiscoverEdges:
    """변수 간 엣지 탐색 테스트."""

    @pytest.mark.asyncio
    async def test_피어슨_상관_임계값_이상_엣지_발견(self):
        """높은 상관관계를 가진 변수 쌍은 엣지로 탐색되어야 한다."""
        data = _make_correlated_data(n=50, noise=0.1)
        edges = await discover_edges(data, methods=["pearson"], threshold=0.3)

        # A와 B는 거의 완벽한 선형 관계 — 엣지가 발견되어야 함
        pairs = {(e.source, e.target) for e in edges}
        assert ("A", "B") in pairs or ("B", "A") in pairs

    @pytest.mark.asyncio
    async def test_피어슨_임계값_미달_엣지_무시(self):
        """임계값보다 낮은 상관관계는 엣지로 포함되지 않아야 한다."""
        data = _make_correlated_data(n=50, noise=0.1)
        # 임계값을 1.0으로 설정 — 완벽한 상관도 약간의 노이즈로 못 넘음
        edges = await discover_edges(data, methods=["pearson"], threshold=1.0)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_데이터_부족_시_엣지_없음(self):
        """데이터 포인트가 10개 미만이면 엣지를 생성하지 않아야 한다."""
        data = {"A": [1.0, 2.0, 3.0], "B": [2.0, 4.0, 6.0]}
        edges = await discover_edges(data, methods=["pearson"], threshold=0.1)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_동일_변수_자기_상관_제외(self):
        """동일 변수 쌍 (A→A) 엣지는 생성되지 않아야 한다."""
        data = _make_correlated_data(n=50)
        edges = await discover_edges(data, methods=["pearson"], threshold=0.1)
        for e in edges:
            assert e.source != e.target, f"자기 엣지 발견: {e.source} → {e.target}"

    @pytest.mark.asyncio
    async def test_중복_제거_최고_신뢰도_유지(self):
        """같은 (source, target) 쌍이 여러 방법으로 탐색되면 최고 confidence만 유지한다."""
        data = _make_correlated_data(n=50, noise=0.1)
        edges = await discover_edges(data, methods=["pearson", "spearman"], threshold=0.3)

        # 같은 (source, target) 쌍이 중복 없이 유지되는지 확인
        pairs = [(e.source, e.target) for e in edges]
        assert len(pairs) == len(set(pairs)), "중복 엣지가 존재합니다"


# ===================================================================
# Step 2: 상관 행렬 (compute_correlation_matrix)
# ===================================================================

class TestCorrelationMatrix:
    """상관 행렬 계산 테스트."""

    @pytest.mark.asyncio
    async def test_상관행렬_대각선_1(self):
        """상관 행렬의 대각선 값은 항상 1.0이어야 한다."""
        data = _make_correlated_data(n=30)
        result = await compute_correlation_matrix(data)
        matrix = result["matrix"]
        for i in range(len(matrix)):
            assert matrix[i][i] == pytest.approx(1.0), f"대각선 [{i}][{i}] != 1.0"

    @pytest.mark.asyncio
    async def test_상관행렬_변수_2개_대칭(self):
        """상관 행렬은 대칭이어야 한다: matrix[i][j] == matrix[j][i]."""
        data = {"X": [1.0, 2.0, 3.0, 4.0, 5.0], "Y": [5.0, 4.0, 3.0, 2.0, 1.0]}
        result = await compute_correlation_matrix(data)
        matrix = result["matrix"]
        assert matrix[0][1] == pytest.approx(matrix[1][0], abs=1e-4)

    @pytest.mark.asyncio
    async def test_빈_데이터_상관행렬(self):
        """빈 데이터는 빈 행렬을 반환해야 한다."""
        result = await compute_correlation_matrix({})
        assert result["variables"] == []
        assert result["matrix"] == []


# ===================================================================
# Step 3: DAG 구축 (build_model_graph)
# ===================================================================

class TestBuildModelGraph:
    """DAG 그래프 구축 테스트."""

    @pytest.mark.asyncio
    async def test_사이클_없는_DAG_구축(self):
        """A→B, B→C 엣지로 유효한 DAG가 구축되어야 한다."""
        edges = [
            EdgeCandidate(source="A", target="B", method=EdgeMethod.PEARSON, confidence=0.9),
            EdgeCandidate(source="B", target="C", method=EdgeMethod.PEARSON, confidence=0.8),
        ]
        graph = await build_model_graph(edges, ["A", "B", "C"])

        assert "A" in graph["B"].parents
        assert "B" in graph["C"].parents
        assert graph["A"].parents == []

    @pytest.mark.asyncio
    async def test_사이클_엣지_거부(self):
        """사이클을 형성하는 엣지는 추가되지 않아야 한다."""
        edges = [
            EdgeCandidate(source="A", target="B", method=EdgeMethod.PEARSON, confidence=0.9),
            EdgeCandidate(source="B", target="A", method=EdgeMethod.PEARSON, confidence=0.5),
        ]
        graph = await build_model_graph(edges, ["A", "B"])

        # 첫 번째 엣지(A→B)는 추가되고, 두 번째(B→A)는 사이클이므로 거부
        assert "A" in graph["B"].parents
        assert "B" not in graph["A"].parents

    @pytest.mark.asyncio
    async def test_빈_엣지_전체_노드_보존(self):
        """엣지가 없어도 모든 노드가 그래프에 보존되어야 한다."""
        graph = await build_model_graph([], ["X", "Y", "Z"])
        assert set(graph.keys()) == {"X", "Y", "Z"}
        for node in graph.values():
            assert node.parents == []


# ===================================================================
# Step 4: 모델 학습 (train_models)
# ===================================================================

class TestTrainModels:
    """노드별 회귀 모델 학습 테스트."""

    @pytest.mark.asyncio
    async def test_부모_있는_노드_학습_성공(self):
        """부모가 있는 노드는 학습 후 r_squared > 0 이어야 한다."""
        pytest.importorskip("sklearn", reason="sklearn 미설치 — 모델 학습 테스트 건너뜀")
        rng = np.random.default_rng(42)
        n = 50
        a_vals = np.linspace(0, 10, n).tolist()
        b_vals = [2.0 * a + 3.0 + rng.normal(0, 0.1) for a in a_vals]

        graph = {
            "A": SimulationNode(variable="A"),
            "B": SimulationNode(variable="B", parents=["A"]),
        }
        data = {"A": a_vals, "B": b_vals}

        result = await train_models(graph, data)
        assert result["B"].is_trained is True
        assert result["B"].r_squared > 0.9  # 거의 완벽한 선형 관계

    @pytest.mark.asyncio
    async def test_부모_없는_노드_즉시_완료(self):
        """부모가 없는 루트 노드는 학습 없이 is_trained=True로 표시된다."""
        graph = {"A": SimulationNode(variable="A")}
        data = {"A": [1.0, 2.0, 3.0]}

        result = await train_models(graph, data)
        assert result["A"].is_trained is True
        assert result["A"].coefficients == {}

    @pytest.mark.asyncio
    async def test_데이터_부족_학습_건너뛰기(self):
        """데이터가 5개 미만이면 학습을 건너뛰어야 한다."""
        graph = {
            "A": SimulationNode(variable="A"),
            "B": SimulationNode(variable="B", parents=["A"]),
        }
        data = {"A": [1.0, 2.0, 3.0], "B": [2.0, 4.0, 6.0]}

        result = await train_models(graph, data)
        # A는 루트 → is_trained=True
        assert result["A"].is_trained is True
        # B는 데이터 부족 → 학습 안됨
        assert result["B"].is_trained is False


# ===================================================================
# Step 5: 모델 검증 (validate_models)
# ===================================================================

class TestValidateModels:
    """모델 백테스팅 검증 테스트."""

    @pytest.mark.asyncio
    async def test_학습된_모델_백테스트(self):
        """학습된 모델은 validation 결과에 rmse, r2_test가 포함되어야 한다."""
        pytest.importorskip("sklearn", reason="sklearn 미설치 — 모델 학습 테스트 건너뜀")
        rng = np.random.default_rng(42)
        n = 100
        a_vals = np.linspace(0, 10, n).tolist()
        b_vals = [2.0 * a + 3.0 + rng.normal(0, 0.1) for a in a_vals]

        graph = {
            "A": SimulationNode(variable="A"),
            "B": SimulationNode(variable="B", parents=["A"]),
        }
        data = {"A": a_vals, "B": b_vals}

        # 먼저 학습
        graph = await train_models(graph, data)
        assert graph["B"].is_trained

        # 검증
        results = await validate_models(graph, data)
        assert results["B"]["status"] == "validated"
        assert "rmse" in results["B"]
        assert "r2_test" in results["B"]

    @pytest.mark.asyncio
    async def test_미학습_모델_스킵(self):
        """학습되지 않은 모델은 status='skipped'이어야 한다."""
        graph = {
            "A": SimulationNode(variable="A"),
            "B": SimulationNode(variable="B", parents=["A"], is_trained=False),
        }
        data = {"A": list(range(100)), "B": list(range(100))}

        results = await validate_models(graph, data)
        assert results["B"]["status"] == "skipped"


# ===================================================================
# Step 6: 시뮬레이션 (simulate)
# ===================================================================

class TestSimulate:
    """DAG 기반 What-if 시뮬레이션 테스트."""

    @pytest.mark.asyncio
    async def test_개입_값_고정_전파(self):
        """개입 변수는 개입 값으로 고정되고 종속 변수가 변경되어야 한다."""
        # A → B (B = 2*A + 3)
        graph = {
            "A": SimulationNode(
                variable="A", is_trained=True,
            ),
            "B": SimulationNode(
                variable="B", parents=["A"], is_trained=True,
                coefficients={"A": 2.0}, intercept=3.0,
            ),
        }
        baseline = {"A": 5.0, "B": 13.0}
        interventions = {"A": 10.0}

        result = await simulate(graph, baseline, interventions)

        # A는 개입 값 10.0으로 고정
        assert result["A"] == 10.0
        # B = 2 * 10 + 3 = 23.0
        assert result["B"] == pytest.approx(23.0, abs=1e-4)

    @pytest.mark.asyncio
    async def test_개입_없으면_베이스라인_유지(self):
        """개입이 없으면 모든 변수가 베이스라인 값을 유지해야 한다."""
        graph = {
            "A": SimulationNode(variable="A", is_trained=True),
            "B": SimulationNode(
                variable="B", parents=["A"], is_trained=True,
                coefficients={"A": 2.0}, intercept=3.0,
            ),
        }
        baseline = {"A": 5.0, "B": 13.0}

        result = await simulate(graph, baseline, interventions={})

        # 개입 없음 — B는 부모(A)의 베이스라인으로 재계산
        # B = 2 * 5.0 + 3.0 = 13.0
        assert result["B"] == pytest.approx(13.0, abs=1e-4)

    @pytest.mark.asyncio
    async def test_위상_정렬_순서_올바름(self):
        """위상 정렬 순서대로 전파되어 부모가 먼저 계산되어야 한다."""
        # A → B → C (B = 2*A, C = 3*B)
        graph = {
            "A": SimulationNode(variable="A", is_trained=True),
            "B": SimulationNode(
                variable="B", parents=["A"], is_trained=True,
                coefficients={"A": 2.0}, intercept=0.0,
            ),
            "C": SimulationNode(
                variable="C", parents=["B"], is_trained=True,
                coefficients={"B": 3.0}, intercept=0.0,
            ),
        }
        baseline = {"A": 1.0, "B": 2.0, "C": 6.0}
        interventions = {"A": 5.0}

        result = await simulate(graph, baseline, interventions)

        # A=5, B=2*5=10, C=3*10=30
        assert result["A"] == 5.0
        assert result["B"] == pytest.approx(10.0, abs=1e-4)
        assert result["C"] == pytest.approx(30.0, abs=1e-4)


# ===================================================================
# Step 7: 시나리오 비교 (compare_scenarios)
# ===================================================================

class TestCompareScenarios:
    """시나리오 비교 분석 테스트."""

    @pytest.mark.asyncio
    async def test_2개_시나리오_비교_델타_계산(self):
        """2개 시나리오의 delta와 delta_pct가 올바르게 계산되어야 한다."""
        s1 = WhatIfScenario(
            id="s1", name="기본",
            results={"X": 100.0, "Y": 50.0},
            baseline={"X": 80.0, "Y": 50.0},
        )
        s2 = WhatIfScenario(
            id="s2", name="공격적",
            results={"X": 120.0, "Y": 60.0},
            baseline={"X": 80.0, "Y": 50.0},
        )
        result = await compare_scenarios([s1, s2])

        assert "comparison" in result
        assert result["scenario_count"] == 2

        # X의 s1: delta = 100 - 80 = 20, pct = 25%
        x_entries = result["comparison"]["X"]
        s1_entry = next(e for e in x_entries if e["scenario_id"] == "s1")
        assert s1_entry["delta"] == pytest.approx(20.0, abs=0.01)
        assert s1_entry["delta_pct"] == pytest.approx(25.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_최대_영향_변수_식별(self):
        """가장 큰 |delta_pct|를 가진 변수가 max_impact_variable로 식별되어야 한다."""
        s1 = WhatIfScenario(
            id="s1", name="a",
            results={"X": 200.0, "Y": 52.0},
            baseline={"X": 100.0, "Y": 50.0},
        )
        s2 = WhatIfScenario(
            id="s2", name="b",
            results={"X": 110.0, "Y": 51.0},
            baseline={"X": 100.0, "Y": 50.0},
        )
        result = await compare_scenarios([s1, s2])

        # X의 s1: delta_pct=100%, Y의 s1: 4% → X가 최대 영향
        assert result["max_impact_variable"] == "X"

    @pytest.mark.asyncio
    async def test_시나리오_1개_에러(self):
        """시나리오가 2개 미만이면 에러 메시지를 반환해야 한다."""
        s1 = WhatIfScenario(id="s1", name="single")
        result = await compare_scenarios([s1])
        assert "error" in result


# ===================================================================
# 위상 정렬 (_topological_sort)
# ===================================================================

class TestTopologicalSort:
    """위상 정렬 알고리즘 테스트."""

    def test_위상_정렬_선형_체인(self):
        """A→B→C 선형 체인은 [A, B, C] 순서로 정렬되어야 한다."""
        graph = _make_graph_abc()
        order = _topological_sort(graph)

        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_위상_정렬_다이아몬드(self):
        """다이아몬드 그래프: A→B, A→C, B→D, C→D → A 먼저, D 마지막."""
        graph = {
            "A": SimulationNode(variable="A"),
            "B": SimulationNode(variable="B", parents=["A"]),
            "C": SimulationNode(variable="C", parents=["A"]),
            "D": SimulationNode(variable="D", parents=["B", "C"]),
        }
        order = _topological_sort(graph)

        assert order[0] == "A"
        assert order[-1] == "D"
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")


# ===================================================================
# 사이클 감지 (_has_cycle)
# ===================================================================

class TestHasCycle:
    """DAG 사이클 감지 테스트."""

    def test_사이클_없음_False(self):
        """사이클이 없는 DAG는 False를 반환해야 한다."""
        graph = _make_graph_abc()
        assert _has_cycle(graph) is False

    def test_사이클_있음_True(self):
        """사이클이 있으면 True를 반환해야 한다."""
        graph = {
            "A": SimulationNode(variable="A", parents=["B"]),
            "B": SimulationNode(variable="B", parents=["A"]),
        }
        assert _has_cycle(graph) is True


# ===================================================================
# 데이터 모델 직렬화/역직렬화
# ===================================================================

class TestDataModels:
    """데이터 모델 직렬화 및 역직렬화 테스트."""

    def test_EdgeCandidate_to_dict(self):
        """EdgeCandidate.to_dict가 올바른 딕셔너리를 반환해야 한다."""
        edge = EdgeCandidate(
            source="A", target="B", method=EdgeMethod.PEARSON,
            correlation=0.85, confidence=0.85,
        )
        d = edge.to_dict()
        assert d["source"] == "A"
        assert d["method"] == "pearson"

    def test_SimulationNode_roundtrip(self):
        """SimulationNode → to_dict → from_dict 왕복 변환이 일관되어야 한다."""
        node = SimulationNode(
            variable="X", parents=["A", "B"],
            coefficients={"A": 1.5, "B": -0.3},
            intercept=2.1, r_squared=0.92, is_trained=True,
        )
        d = node.to_dict()
        restored = SimulationNode.from_dict(d)
        assert restored.variable == node.variable
        assert restored.parents == node.parents
        assert restored.coefficients == node.coefficients
        assert restored.is_trained is True

    def test_WhatIfScenario_roundtrip(self):
        """WhatIfScenario → to_dict → from_dict 왕복 변환이 일관되어야 한다."""
        scenario = WhatIfScenario(
            id="test-id", name="테스트 시나리오",
            interventions={"A": 10.0},
            results={"A": 10.0, "B": 23.0},
            baseline={"A": 5.0, "B": 13.0},
            tenant_id="t1",
        )
        d = scenario.to_dict()
        restored = WhatIfScenario.from_dict(d)
        assert restored.id == "test-id"
        assert restored.name == "테스트 시나리오"
        assert restored.interventions == {"A": 10.0}
        assert restored.tenant_id == "t1"
