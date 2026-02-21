import pytest
import pandas as pd
from datetime import datetime, timedelta
from app.mining.process_discovery import (
    discover_with_alpha, discover_with_heuristic, discover_with_inductive, generate_bpmn
)

def generate_mock_log() -> pd.DataFrame:
    """Generate a valid mock event log DataFrame for pm4py."""
    now = datetime.now()
    data = [
        {"case:concept:name": "1", "concept:name": "A", "time:timestamp": now},
        {"case:concept:name": "1", "concept:name": "B", "time:timestamp": now + timedelta(seconds=1)},
        {"case:concept:name": "1", "concept:name": "C", "time:timestamp": now + timedelta(seconds=2)},
        
        {"case:concept:name": "2", "concept:name": "A", "time:timestamp": now},
        {"case:concept:name": "2", "concept:name": "B", "time:timestamp": now + timedelta(seconds=2)},
        {"case:concept:name": "2", "concept:name": "C", "time:timestamp": now + timedelta(seconds=3)},
    ]
    df = pd.DataFrame(data)
    # Convert timestamp to proper datetime format expected by pm4py
    df['time:timestamp'] = pd.to_datetime(df['time:timestamp'], utc=True)
    return df

@pytest.mark.asyncio
async def test_discover_with_alpha():
    df = generate_mock_log()
    result = await discover_with_alpha(df)
    assert result.algorithm == "alpha"
    assert result.statistics["transitions"] >= 3
    assert result.petri_net is not None

@pytest.mark.asyncio
async def test_discover_with_heuristic():
    df = generate_mock_log()
    result = await discover_with_heuristic(df, dependency_threshold=0.5)
    assert result.algorithm == "heuristic"
    assert result.statistics["dependency_threshold"] == 0.5
    assert result.petri_net is not None

@pytest.mark.asyncio
async def test_discover_with_inductive():
    df = generate_mock_log()
    result = await discover_with_inductive(df, noise_threshold=0.2)
    assert result.algorithm == "inductive"
    assert result.statistics["is_sound"] is True
    assert result.petri_net is not None

@pytest.mark.asyncio
async def test_generate_bpmn():
    df = generate_mock_log()
    xml_str = await generate_bpmn(df)
    assert "bpmn:definitions" in xml_str
    assert "bpmn:process" in xml_str
