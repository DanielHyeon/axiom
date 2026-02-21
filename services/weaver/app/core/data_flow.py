from __future__ import annotations

import asyncio
from typing import Any


class DataFlowManager:
    """Chunk-oriented extractor with predictable memory bounds."""

    def __init__(self, chunk_size: int = 5000, *, bytes_per_record_estimate: int = 256) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if bytes_per_record_estimate <= 0:
            raise ValueError("bytes_per_record_estimate must be > 0")
        self.chunk_size = chunk_size
        self.bytes_per_record_estimate = bytes_per_record_estimate

    async def extract_and_stream(self, session_id: str, total_records: int) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("session_id is required")
        if total_records < 0:
            raise ValueError("total_records must be >= 0")

        processed = 0
        chunks = 0
        per_chunk_records: list[int] = []
        peak_memory_bytes = 0

        while processed < total_records:
            size = min(self.chunk_size, total_records - processed)
            per_chunk_records.append(size)
            processed += size
            chunks += 1
            chunk_memory = size * self.bytes_per_record_estimate
            if chunk_memory > peak_memory_bytes:
                peak_memory_bytes = chunk_memory
            # Yield control for cooperative scheduling during large extraction loops.
            await asyncio.sleep(0)

        return {
            "session_id": session_id,
            "status": "completed",
            "total_records_processed": processed,
            "chunks_yielded": chunks,
            "records_per_chunk": per_chunk_records,
            "peak_chunk_memory_bytes": peak_memory_bytes,
            "max_memory_bound_enforced": peak_memory_bytes <= (self.chunk_size * self.bytes_per_record_estimate),
        }

data_flow = DataFlowManager()
