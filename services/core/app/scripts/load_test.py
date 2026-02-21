import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("load_tester")

async def hit_health_endpoint(client: httpx.AsyncClient, i: int):
    start = time.time()
    resp = await client.get("http://localhost:8000/api/v1/health/live")
    elapsed = time.time() - start
    return resp.status_code, elapsed

async def run_load_test(requests: int = 100):
    logger.info(f"Starting load test with {requests} requests...")
    start_total = time.time()
    
    async with httpx.AsyncClient() as client:
        tasks = [hit_health_endpoint(client, i) for i in range(requests)]
        results = await asyncio.gather(*tasks)
        
    total_time = time.time() - start_total
    
    successes = sum(1 for r, _ in results if r == 200)
    avg_latency = sum(lat for _, lat in results) / len(results) if results else 0
    
    logger.info(f"Requests: {requests}")
    logger.info(f"Success Ratio: {successes}/{requests} ({(successes/requests)*100:.1f}%)")
    logger.info(f"Total Time: {total_time:.2f}s")
    logger.info(f"Avg Latency: {avg_latency*1000:.2f}ms")
    logger.info(f"Throughput: {requests/total_time:.2f} req/s")

if __name__ == "__main__":
    asyncio.run(run_load_test(200))
