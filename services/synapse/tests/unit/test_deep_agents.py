"""Deep Agents 5계층 생성기 + SSE 스트리밍 단위 테스트."""
import asyncio
import pytest
from app.core.sse_stream import SSEStream
from app.services.deep_agents.quality_evaluator import evaluate_layer, QualityResult
from app.services.deep_agents.layer_agents import (
    KPIAgent, MeasureAgent, DriverAgent, ProcessAgent, ResourceAgent, LayerSchema,
)


class TestSSEStream:
    @pytest.mark.asyncio
    async def test_emit_and_iterate(self):
        stream = SSEStream(maxsize=10)
        stream.emit({"event": "start"})
        stream.emit({"event": "progress", "value": 50})
        stream.complete()
        events = []
        async for ev in stream:
            events.append(ev)
        assert len(events) == 2
        assert '"start"' in events[0]

    @pytest.mark.asyncio
    async def test_complete_drains_queue(self):
        stream = SSEStream()
        for i in range(5):
            stream.emit({"i": i})
        stream.complete()
        count = 0
        async for _ in stream:
            count += 1
        assert count == 5

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        stream = SSEStream()
        stream.complete()
        events = []
        async for ev in stream:
            events.append(ev)
        assert len(events) == 0


class TestQualityEvaluator:
    def test_empty_layer(self):
        schema = LayerSchema(layer="kpi", nodes=[], relationships=[])
        result = evaluate_layer(schema)
        assert isinstance(result, QualityResult)
        assert result.confidence <= 0.2

    def test_single_node(self):
        schema = LayerSchema(layer="kpi", nodes=[{"id": "n1", "name": "OEE"}], relationships=[])
        result = evaluate_layer(schema)
        assert result.confidence <= 0.5

    def test_many_nodes(self):
        nodes = [{"id": f"n{i}", "name": f"N{i}"} for i in range(5)]
        schema = LayerSchema(layer="kpi", nodes=nodes, relationships=[])
        result = evaluate_layer(schema)
        assert result.confidence >= 0.6

    def test_result_attributes(self):
        schema = LayerSchema(layer="measure", nodes=[{"id": "n1"}], relationships=[])
        result = evaluate_layer(schema)
        assert hasattr(result, "confidence")
        assert hasattr(result, "node_count")


class TestLayerAgents:
    def test_kpi(self): assert KPIAgent().layer_type == "kpi"
    def test_measure(self): assert MeasureAgent().layer_type == "measure"
    def test_driver(self): assert DriverAgent().layer_type == "driver"
    def test_process(self): assert ProcessAgent().layer_type == "process"
    def test_resource(self): assert ResourceAgent().layer_type == "resource"
    def test_all_have_prompt(self):
        for Cls in [KPIAgent, MeasureAgent, DriverAgent, ProcessAgent, ResourceAgent]:
            assert Cls().system_prompt


class TestLayerSchema:
    def test_create(self):
        s = LayerSchema(layer="kpi", nodes=[{"id": "1"}], relationships=[{"src": "1", "tgt": "2"}])
        assert s.layer == "kpi" and len(s.nodes) == 1

    def test_empty(self):
        s = LayerSchema(layer="driver", nodes=[], relationships=[])
        assert len(s.nodes) == 0
