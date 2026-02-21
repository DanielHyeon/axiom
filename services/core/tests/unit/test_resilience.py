import pytest
from app.core.resilience import circuit_breaker, CircuitOpenException

@pytest.mark.asyncio
async def test_circuit_breaker_closes_on_failures():
    
    @circuit_breaker(max_failures=2, reset_timeout=10)
    async def flaky_api(succeed: bool):
        if not succeed:
            raise ValueError("Upstream failure")
        return "OK"
        
    # Failure 1
    with pytest.raises(ValueError):
        await flaky_api(False)
        
    # Failure 2 (Trips circuit)
    with pytest.raises(ValueError):
        await flaky_api(False)
        
    # Failure 3 (Fast fail - Circuit open)
    with pytest.raises(CircuitOpenException, match="Circuit is OPEN"):
        await flaky_api(True) # Even if we ask it to succeed, it fails fast
