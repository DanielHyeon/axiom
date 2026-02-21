import pm4py
import pandas as pd
from typing import Any, Dict, Optional
from pydantic import BaseModel

class DiscoveryResult(BaseModel):
    algorithm: str
    statistics: Dict[str, Any]
    petri_net: Any
    initial_marking: Any
    final_marking: Any

    class Config:
        arbitrary_types_allowed = True

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
