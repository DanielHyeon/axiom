import pytest
from app.llm.agent import HITLAgentRouter

def test_confidence_calculations():
    # Base 0.5, Tools Verified (+0.1) -> 0.6
    res1 = {"confidence": 0.5, "tools_verified": True}
    assert HITLAgentRouter.calculate_confidence(res1) == pytest.approx(0.6)
    
    # Base 0.9, No adjustments -> 0.9
    res2 = {"confidence": 0.9}
    assert HITLAgentRouter.calculate_confidence(res2) == pytest.approx(0.9)
    
    # Base 0.8, Requires Expert (-0.2) -> 0.6
    res3 = {"confidence": 0.8, "requires_expert_judgment": True}
    assert HITLAgentRouter.calculate_confidence(res3) == pytest.approx(0.6)
    
    # Limits max 1.0
    res4 = {"confidence": 0.95, "tools_verified": True}
    assert HITLAgentRouter.calculate_confidence(res4) == pytest.approx(1.0)

def test_agent_routing_states():
    assert HITLAgentRouter.determine_next_state(0.99) == "DONE"
    assert HITLAgentRouter.determine_next_state(1.0) == "DONE"
    
    assert HITLAgentRouter.determine_next_state(0.98) == "SUBMITTED"
    assert HITLAgentRouter.determine_next_state(0.80) == "SUBMITTED"
    
    assert HITLAgentRouter.determine_next_state(0.79) == "TODO"
    assert HITLAgentRouter.determine_next_state(0.40) == "TODO"
