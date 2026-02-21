import time
from functools import wraps

class CircuitOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, max_failures: int = 3, reset_timeout: int = 60):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF_OPEN

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.max_failures:
            self.state = "OPEN"

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
            
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
            
        # HALF_OPEN
        return True

def circuit_breaker(max_failures=3, reset_timeout=60):
    cb = CircuitBreaker(max_failures, reset_timeout)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not cb.allow_request():
                raise CircuitOpenException("Circuit is OPEN. Failing fast.")
                
            try:
                result = await func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                if not isinstance(e, CircuitOpenException):
                    cb.record_failure()
                raise e
        return wrapper
    return decorator
