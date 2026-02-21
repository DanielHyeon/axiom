import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger("axiom.workers")

class BaseWorker:
    def __init__(self, name: str):
        self.name = name
        self._running = True

    async def start(self):
        logger.info(f"Worker {self.name} started")
        await self.run()

    async def run(self):
        raise NotImplementedError

    def _shutdown(self):
        logger.info(f"Worker {self.name} shutting down...")
        self._running = False

    async def process_with_retry(self, func: Callable, *args: Any, max_retries: int = 3):
        for attempt in range(max_retries):
            try:
                return await func(*args)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Worker task failed permanently after {max_retries} attempts.")
                    raise
                wait = 2 ** attempt
                logger.warning(f"Retry {attempt+1}/{max_retries} for {func.__name__}: {e}")
                await asyncio.sleep(wait)

    async def process_event_idempotent(self, redis, event_id: str, handler: Callable):
        """Idempotency wrapper using Redis SETNX."""
        dedup_key = f"event:processed:{event_id}"
        
        is_new = await redis.set(dedup_key, "1", nx=True, ex=7 * 86400)
        if not is_new:
            logger.debug(f"Skipping duplicate event: {event_id}")
            return
            
        try:
            await handler()
        except Exception:
            await redis.delete(dedup_key)
            raise
