import logging
from typing import Dict, Any

logger = logging.getLogger("axiom.llm.agent")

class HITLAgentRouter:
    """
    Evaluates LLM execution confidence and determines the next state 
    for the WorkItem according to the 3-tier HITL model.
    """
    
    @staticmethod
    def calculate_confidence(agent_result: Dict[str, Any]) -> float:
        base_confidence = float(agent_result.get("confidence", 0.5))
        adjustments = 0.0

        if agent_result.get("tools_verified"):
            adjustments += 0.1
            
        historical_accuracy = float(agent_result.get("historical_accuracy", 0.0))
        adjustments += historical_accuracy * 0.1
        
        if agent_result.get("requires_expert_judgment"):
            adjustments -= 0.2

        return min(max(base_confidence + adjustments, 0.0), 1.0)

    @staticmethod
    def determine_next_state(confidence: float) -> str:
        """
        >= 0.99 -> DONE
        0.80 ~ 0.99 -> SUBMITTED (HITL Review)
        < 0.80 -> TODO (Manual intervention)
        """
        if confidence >= 0.99:
            return "DONE"
        elif confidence >= 0.80:
            return "SUBMITTED"
        return "TODO"

class PseudoReActAgent:
    """Mock implementation of LangGraph create_react_agent"""
    
    @staticmethod
    async def execute_task(workitem_data: dict, activity_spec: dict) -> dict:
        # Pseudo execution representing an LLM interacting with tools
        logger.info(f"Executing LLM task for {activity_spec.get('name')}")
        
        # Mocking an observation
        is_complex = activity_spec.get("is_complex", False)
        
        raw_result = {
            "output": "Extracted metrics successfully.",
            "confidence": 0.85 if not is_complex else 0.65,
            "tools_verified": True,
            "requires_expert_judgment": is_complex
        }
        
        final_confidence = HITLAgentRouter.calculate_confidence(raw_result)
        next_status = HITLAgentRouter.determine_next_state(final_confidence)
        
        return {
            "result": raw_result["output"],
            "calculated_confidence": final_confidence,
            "suggested_status": next_status
        }
