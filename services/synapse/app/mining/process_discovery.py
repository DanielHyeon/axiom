import asyncio
import pm4py
import pandas as pd
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


def events_to_pm4py_dataframe(events: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Synapse 이벤트 리스트(case_id, activity, timestamp)를 pm4py 표준 DataFrame으로 변환.
    pm4py 컬럼: case:concept:name, concept:name, time:timestamp
    """
    if not events:
        return pd.DataFrame(columns=["case:concept:name", "concept:name", "time:timestamp"])
    rows = [
        {
            "case:concept:name": str(e.get("case_id", "")),
            "concept:name": str(e.get("activity", "")),
            "time:timestamp": pd.to_datetime(e.get("timestamp"), utc=True),
        }
        for e in events
    ]
    df = pd.DataFrame(rows)
    return pm4py.format_dataframe(
        df,
        case_id="case:concept:name",
        activity_key="concept:name",
        timestamp_key="time:timestamp",
    )

class DiscoveryResult(BaseModel):
    algorithm: str
    statistics: Dict[str, Any]
    petri_net: Any
    initial_marking: Any
    final_marking: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

async def discover_with_alpha(df: pd.DataFrame) -> DiscoveryResult:
    """
    Alpha Miner: basic process discovery.
    Best for structured, noise-free logs.
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty")
        
    net, initial_marking, final_marking = pm4py.discover_petri_net_alpha(df)
    
    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
    }
    
    return DiscoveryResult(
        algorithm="alpha",
        petri_net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        statistics=stats
    )

async def discover_with_heuristic(df: pd.DataFrame, dependency_threshold: float = 0.5) -> DiscoveryResult:
    """
    Heuristic Miner: noise-tolerant process discovery.
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty")
        
    net, initial_marking, final_marking = pm4py.discover_petri_net_heuristics(
        df, dependency_threshold=dependency_threshold
    )
    
    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "dependency_threshold": dependency_threshold,
    }
    
    return DiscoveryResult(
        algorithm="heuristic",
        petri_net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        statistics=stats
    )

async def discover_with_inductive(df: pd.DataFrame, noise_threshold: float = 0.2) -> DiscoveryResult:
    """
    Inductive Miner: guaranteed sound model.
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty")
        
    net, initial_marking, final_marking = pm4py.discover_petri_net_inductive(
        df, noise_threshold=noise_threshold
    )
    
    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "noise_threshold": noise_threshold,
        "is_sound": True, 
    }
    
    return DiscoveryResult(
        algorithm="inductive",
        petri_net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        statistics=stats
    )

async def generate_bpmn(df: pd.DataFrame) -> str:
    """
    Generate BPMN model directly from event log.
    Returns BPMN 2.0 XML string.
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty")
        
    bpmn_model = pm4py.discover_bpmn_inductive(df)
    import tempfile, os
    from pm4py.objects.bpmn.exporter import exporter as bpmn_exporter
    
    with tempfile.NamedTemporaryFile(suffix='.bpmn', delete=False) as f:
        bpmn_exporter.apply(bpmn_model, f.name)
        with open(f.name, 'r') as xml_file:
            bpmn_xml = xml_file.read()
        os.unlink(f.name)

    return bpmn_xml


def _petri_to_bpmn_xml(net: Any, initial_marking: Any, final_marking: Any) -> str:
    """Petri net을 BPMN 모델로 변환 후 XML 문자열 반환."""
    import os
    import tempfile
    from pm4py.convert import convert_to_bpmn
    from pm4py.objects.bpmn.exporter import exporter as bpmn_exporter
    bpmn_model = convert_to_bpmn(net, initial_marking, final_marking)
    with tempfile.NamedTemporaryFile(suffix='.bpmn', delete=False) as f:
        bpmn_exporter.apply(bpmn_model, f.name)
        with open(f.name, 'r') as xml_file:
            xml = xml_file.read()
        os.unlink(f.name)
    return xml


def run_discover_sync(
    algorithm: str,
    df: pd.DataFrame,
    noise_threshold: float = 0.2,
    dependency_threshold: float = 0.5,
    generate_bpmn: bool = True,
) -> tuple[dict[str, Any], str | None]:
    """
    동기 래퍼: algorithm에 따라 discovery 실행 후 model 통계와 BPMN XML 반환.
    Returns (model_dict for result["model"], bpmn_xml or None).
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty")
    if algorithm == "alpha":
        discovery = asyncio.run(discover_with_alpha(df))
    elif algorithm == "heuristic":
        discovery = asyncio.run(discover_with_heuristic(df, dependency_threshold=dependency_threshold))
    else:
        discovery = asyncio.run(discover_with_inductive(df, noise_threshold=noise_threshold))
    activities = []
    if hasattr(discovery.petri_net, "transitions"):
        for t in discovery.petri_net.transitions:
            label = getattr(t, "label", getattr(t, "name", str(t)))
            if label and not str(label).startswith("tau"):
                activities.append(str(label))
    model = {
        "type": "petri_net",
        "places": discovery.statistics.get("places", 0),
        "transitions": discovery.statistics.get("transitions", 0),
        "arcs": discovery.statistics.get("arcs", 0),
        "activities": sorted(set(activities)),
    }
    bpmn_xml = None
    if generate_bpmn:
        try:
            bpmn_xml = _petri_to_bpmn_xml(
                discovery.petri_net,
                discovery.initial_marking,
                discovery.final_marking,
            )
        except Exception:
            pass
    return model, bpmn_xml
