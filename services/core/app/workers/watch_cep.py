"""Backward compatibility shim.

신규 코드는 app.modules.watch.infrastructure.watch_cep를 직접 import해야 한다.
"""
from app.modules.watch.infrastructure.watch_cep import (  # noqa: F401
    WatchCepWorker,
)

if __name__ == "__main__":
    import asyncio
    asyncio.run(WatchCepWorker().start())
